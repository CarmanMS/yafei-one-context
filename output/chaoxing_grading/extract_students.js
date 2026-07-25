const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = process.argv[2] || '.';

const markUrl = 'https://mooc2-ans.chaoxing.com/mooc2-ans/work/mark?courseid=265063201&clazzid=0&id=129157074&cpi=35042781&evaluation=0&from=&v=0&prePageNum=1&prePageSize=20&topicid=0&perspectiveType=0';

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

async function extractStudentList() {
  const page = await getCDPPage();
  const { ws, send } = createCDPConnection(page.webSocketDebuggerUrl);

  await new Promise((resolve) => {
    ws.addEventListener('open', resolve);
  });

  await send('Page.enable');
  await send('Runtime.enable');

  console.log('Navigating to mark list...');
  await send('Page.navigate', { url: markUrl });

  // Wait for page load
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

  await new Promise(r => setTimeout(r, 4000));

  console.log('Extracting student list...');
  const result = await send('Runtime.evaluate', {
    expression: `(() => {
      const students = [];
      const rows = document.querySelectorAll('ul.dataBody_td');
      rows.forEach(row => {
        const nameEl = row.querySelector('.py_name');
        const name = nameEl ? nameEl.textContent.trim() : '';
        
        const tds = row.querySelectorAll('li.taskBody_con');
        const studentId = tds[0] ? tds[0].textContent.trim() : '';
        const submitTime = tds[1] ? tds[1].textContent.trim() : '';
        const ip = tds[2] ? tds[2].textContent.trim() : '';
        const status = tds[3] ? tds[3].textContent.trim() : '';
        
        const markLink = row.querySelector('a.cz_py');
        const data = markLink ? markLink.getAttribute('data') : '';
        
        const scoreInput = row.querySelector('input.scoreInput');
        const scoreValue = scoreInput ? scoreInput.value : '';
        
        if (name && studentId) {
          students.push({
            name,
            studentId,
            submitTime,
            ip,
            status,
            data,
            scoreValue
          });
        }
      });
      return JSON.stringify(students);
    })()`,
    returnByValue: true
  });

  const students = JSON.parse(result.result.result.value || '[]');
  console.log('Found', students.length, 'students');
  
  // Build review URLs from data attributes
  students.forEach(s => {
    if (s.data) {
      s.reviewUrl = 'https://mooc2-ans.chaoxing.com' + s.data;
    }
  });

  // Save raw student list
  fs.writeFileSync(path.join(OUTPUT_DIR, 'students.json'), JSON.stringify(students, null, 2));
  console.log('Saved students.json');

  // Create grading template
  const gradingTemplate = {
    assignment: {
      title: '现代几何学报告',
      class: '25数学1班',
      totalStudents: students.length,
      fullScore: 100
    },
    students: students.map(s => ({
      name: s.name,
      studentId: s.studentId,
      submitTime: s.submitTime,
      status: s.status,
      reviewUrl: s.reviewUrl,
      score: null,    // to be filled
      comment: '',    // to be filled
      imageUrls: []   // to be filled
    }))
  };

  fs.writeFileSync(path.join(OUTPUT_DIR, 'grading.json'), JSON.stringify(gradingTemplate, null, 2));
  console.log('Saved grading.json');

  ws.close();
  return students;
}

extractStudentList().catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});
