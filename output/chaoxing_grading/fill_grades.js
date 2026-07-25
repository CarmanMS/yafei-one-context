const http = require('http');
const fs = require('fs');

const INPUT_JSON = process.argv[2] || 'grading.json';

const gradingData = JSON.parse(fs.readFileSync(INPUT_JSON, 'utf-8'));
const students = gradingData.students;
const scoredStudents = students.filter(s => s.score !== null && s.score !== undefined);

console.log(`Found ${scoredStudents.length}/${students.length} students with scores to fill.`);

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

async function fillGrades() {
  if (scoredStudents.length === 0) {
    console.log('No students to grade. Please fill in scores in grading.json first.');
    process.exit(1);
  }

  const page = await getCDPPage();
  const { ws, send } = createCDPConnection(page.webSocketDebuggerUrl);

  await new Promise((resolve) => {
    ws.addEventListener('open', resolve);
  });

  await send('Page.enable');
  await send('Runtime.enable');

  for (let i = 0; i < scoredStudents.length; i++) {
    const student = scoredStudents[i];
    console.log(`\n[${i+1}/${scoredStudents.length}] ${student.name} (${student.studentId}) -> Score: ${student.score}`);

    // Navigate to review page
    await send('Page.navigate', { url: student.reviewUrl });
    
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

    // Fill score
    const scoreInputId = 'score129205692'; // The question score input ID
    const scoreResult = await send('Runtime.evaluate', {
      expression: `(() => {
        const input = document.getElementById('${scoreInputId}');
        if (input) {
          input.value = '${student.score}';
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
          return 'Score filled: ' + input.value;
        }
        return 'Score input not found';
      })()`,
      returnByValue: true
    });
    console.log('  ', scoreResult.result.result.value);

    // Fill comment
    const commentId = `comment${student.reviewUrl.match(/workAnswerId=(\d+)/)?.[1] || ''}`;
    if (student.comment) {
      const commentResult = await send('Runtime.evaluate', {
        expression: `(() => {
          const textarea = document.getElementById('${commentId}');
          if (textarea) {
            textarea.value = '${student.comment.replace(/'/g, "\\'").replace(/\n/g, '\\n')}';
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            return 'Comment filled: ' + textarea.value.substring(0, 50) + '...';
          }
          return 'Comment textarea not found: ${commentId}';
        })()`,
        returnByValue: true
      });
      console.log('  ', commentResult.result.result.value);
    }

    // Submit
    const submitResult = await send('Runtime.evaluate', {
      expression: `(() => {
        const btn = document.querySelector('a[onclick="markAction(1)"]');
        if (btn) {
          btn.click();
          return 'Submitted (single)';
        }
        return 'Submit button not found';
      })()`,
      returnByValue: true
    });
    console.log('  ', submitResult.result.result.value);

    await new Promise(r => setTimeout(r, 3000)); // Wait for submission to process
  }

  console.log('\nAll grades filled!');
  ws.close();
}

fillGrades().catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});
