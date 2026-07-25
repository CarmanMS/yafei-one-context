const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

const INPUT_JSON = process.argv[2] || 'grading.json';
const OUTPUT_DIR = process.argv[3] || './submissions';

const gradingData = JSON.parse(fs.readFileSync(INPUT_JSON, 'utf-8'));
const students = gradingData.students;

if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

function getCDPPage() {
  return new Promise((resolve, reject) => {
    http.get('http://localhost:9222/json', (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const pages = JSON.parse(data);
        const page = pages.find(p => p.type === 'page');
        if (!page) reject(new Error('No page found'));
        else resolve(page);
      });
    }).on('error', reject);
  });
}

function createCDPConnection(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let msgId = 0;
  const pending = new Map();

  ws.addEventListener('message', (msg) => {
    const parsed = JSON.parse(msg.data);
    if (parsed.id && pending.has(parsed.id)) {
      pending.get(parsed.id)(parsed);
      pending.delete(parsed.id);
    }
  });

  const send = (method, params = {}) => new Promise((resolve) => {
    const id = ++msgId;
    pending.set(id, resolve);
    ws.send(JSON.stringify({ id, method, params }));
  });

  return { ws, send };
}

async function downloadImage(url, destPath, cookieHeader) {
  return new Promise((resolve) => {
    const req = https.get(url, {
      headers: {
        'Cookie': cookieHeader,
        'Referer': 'https://mooc2-ans.chaoxing.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      }
    }, (resp) => {
      if (resp.statusCode >= 300 && resp.statusCode < 400 && resp.headers.location) {
        resp.resume();
        const newUrl = resp.headers.location.startsWith('http') 
          ? resp.headers.location 
          : new URL(resp.headers.location, url).href;
        downloadImage(newUrl, destPath, cookieHeader).then(resolve);
        return;
      }
      const chunks = [];
      resp.on('data', chunk => chunks.push(chunk));
      resp.on('end', () => {
        const buffer = Buffer.concat(chunks);
        fs.writeFileSync(destPath, buffer);
        console.log('    Saved:', path.basename(destPath), '(' + buffer.length + ' bytes)');
        resolve({ success: true, size: buffer.length });
      });
    });
    req.on('error', (e) => {
      console.log('    Error:', e.message);
      resolve({ success: false, error: e.message });
    });
  });
}

async function extractAllImages() {
  const page = await getCDPPage();
  const { ws, send } = createCDPConnection(page.webSocketDebuggerUrl);

  await new Promise((resolve) => {
    ws.addEventListener('open', resolve);
  });

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');

  // Get cookies
  const cookieResult = await send('Network.getCookies', {
    urls: ['https://p.ananas.chaoxing.com/', 'https://mooc2-ans.chaoxing.com/']
  });
  const cookies = cookieResult.result.cookies || [];
  const cookieHeader = cookies.map(c => `${c.name}=${c.value}`).join('; ');
  console.log('Got', cookies.length, 'cookies');

  // Process each student
  for (let i = 0; i < students.length; i++) {
    const student = students[i];
    console.log(`\n[${i+1}/${students.length}] ${student.name} (${student.studentId})`);
    
    const studentDir = path.join(OUTPUT_DIR, `${student.studentId}_${student.name}`);
    if (!fs.existsSync(studentDir)) fs.mkdirSync(studentDir, { recursive: true });

    // Navigate to student's review page
    await send('Page.navigate', { url: student.reviewUrl });
    
    // Wait for load
    await new Promise((resolve) => {
      const fn = (msg) => {
        const parsed = JSON.parse(msg.data);
        if (parsed.method === 'Page.loadEventFired') {
          ws.removeEventListener('message', fn);
          resolve();
        }
      };
      ws.addEventListener('message', fn);
    });
    await new Promise(r => setTimeout(r, 3000));

    // Extract image URLs from the page
    const imgResult = await send('Runtime.evaluate', {
      expression: `(() => {
        const imgs = Array.from(document.querySelectorAll('img.ans-ued-img'));
        return JSON.stringify(imgs.map(img => img.src));
      })()`,
      returnByValue: true
    });

    const imageUrls = JSON.parse(imgResult.result.result.value || '[]');
    console.log('  Found', imageUrls.length, 'images');
    student.imageUrls = imageUrls;

    // Download each image
    for (let j = 0; j < imageUrls.length; j++) {
      const imgUrl = imageUrls[j];
      const destPath = path.join(studentDir, `img${j+1}.jpg`);
      await downloadImage(imgUrl, destPath, cookieHeader);
    }
  }

  // Save updated grading.json
  fs.writeFileSync(INPUT_JSON, JSON.stringify(gradingData, null, 2));
  console.log('\nUpdated grading.json with image URLs');

  ws.close();
}

extractAllImages().catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});
