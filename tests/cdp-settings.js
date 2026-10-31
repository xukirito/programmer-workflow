// Minimal Chrome DevTools Protocol driver used to verify the DSH Settings page.
// Requires Node 22+ (global WebSocket/fetch).
const fs = require('node:fs');

const PORT = process.env.CDP_PORT || '9223';
const OUT = process.env.CDP_OUT || 'settings-check.png';

async function main() {
  const pages = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = pages.find((item) => item.type === 'page');
  if (!page) throw new Error('no page target: ' + JSON.stringify(pages));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  let nextId = 0;
  const pending = new Map();
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (!message.id) return;
    const entry = pending.get(message.id);
    if (!entry) return;
    pending.delete(message.id);
    if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
    else entry.resolve(message.result);
  };
  function send(method, params) {
    const id = ++nextId;
    ws.send(JSON.stringify({ id, method, params: params || {} }));
    return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
  }
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  async function evaluate(expression) {
    const result = await send('Runtime.evaluate', {
      expression, awaitPromise: true, returnByValue: true, userGesture: true,
    });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  await send('Runtime.enable');
  await send('Page.enable');
  await sleep(8000);
  console.log('TITLE:', await evaluate('document.title'));
  console.log('URL:', await evaluate('location.href'));
  const text = await evaluate('document.body ? document.body.innerText.slice(0,4000) : "NO BODY"');
  console.log('BODY:\n' + text);
  const buttons = await evaluate(`Array.from(document.querySelectorAll('button')).map((b,i)=>({i,text:(b.innerText||'').trim(),aria:b.getAttribute('aria-label')||'',title:b.getAttribute('title')||''}))`);
  console.log('BUTTONS:', JSON.stringify(buttons));
  const settings = buttons.find((b) => /设置|settings/i.test(b.text + ' ' + b.aria + ' ' + b.title));
  if (settings) {
    await evaluate(`document.querySelectorAll('button')[${settings.i}].click()`);
    await sleep(1500);
    console.log('AFTER SETTINGS:\n' + await evaluate('document.body.innerText.slice(0,6000)'));
    const tabs = await evaluate(`Array.from(document.querySelectorAll('button,a')).map((b,i)=>({i,tag:b.tagName,text:(b.innerText||'').trim(),aria:b.getAttribute('aria-label')||''}))`);
    console.log('TABS:', JSON.stringify(tabs.filter((x) => /程序员|workflow|general|general/i.test(x.text + x.aria))));
    const tab = tabs.find((x) => /程序员\s*工作流|Programmer Workflow/i.test(x.text));
    if (tab) {
      await evaluate(`document.querySelectorAll('button,a')[${tab.i}].click()`);
      await sleep(1200);
      console.log('SETTINGS PAGE:\n' + await evaluate('document.body.innerText.slice(0,8000)'));
    }
  } else {
    console.log('NO SETTINGS BUTTON');
  }
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(OUT, Buffer.from(shot.data, 'base64'));
  console.log('SCREENSHOT:', OUT);
  ws.close();
}

main().catch((error) => {
  console.error('CDP ERROR:', error);
  process.exitCode = 1;
});
