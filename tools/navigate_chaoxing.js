// Open chaoxing login page via CDP
const WebSocket = require('ws');
const http = require('http');

// Get existing pages
http.get('http://localhost:9222/json', (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    const pages = JSON.parse(data);
    const firstPage = pages.find(p => p.type === 'page');
    console.log('Existing page:', firstPage?.url || 'none');
    
    // Navigate to chaoxing
    const ws = new WebSocket(firstPage.webSocketDebuggerUrl);
    ws.on('open', () => {
      console.log('Connected to Chrome DevTools');
      ws.send(JSON.stringify({
        id: 1,
        method: 'Page.navigate',
        params: {
          url: 'https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/tch?courseid=265063201&clazzid=149863413&cpi=35042781&enc=b0919652fb3942532ca87cc819ee56a2&t=1783125542386&pageHeader=6&v=2&hideHead=0&perspectiveType='
        }
      }));
    });
    ws.on('message', msg => {
      console.log('Response:', msg);
      ws.close();
    });
  });
});
