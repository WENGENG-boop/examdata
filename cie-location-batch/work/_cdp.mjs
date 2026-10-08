// Minimal CDP client over Node built-in WebSocket (Node >= 22).
// Usage:
//   node _cdp.mjs <port> tabs
//   node _cdp.mjs <port> nav <url>
//   node _cdp.mjs <port> scroll <y>
//   node _cdp.mjs <port> shot <file>
//   node _cdp.mjs <port> eval <expression>
const [, , portArg, cmd, ...args] = process.argv;
const port = Number(portArg || 9223);

async function listTargets() {
  const r = await fetch(`http://127.0.0.1:${port}/json/list`);
  if (!r.ok) throw new Error(`/json/list HTTP ${r.status}`);
  return await r.json();
}

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const t = setTimeout(() => reject(new Error('ws connect timeout')), 8000);
    ws.onopen = () => { clearTimeout(t); resolve(ws); };
    ws.onerror = (e) => { clearTimeout(t); reject(new Error('ws error: ' + (e.message || 'unknown'))); };
  });
}

let seq = 0;
function send(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    const onMsg = (ev) => {
      let m;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id === id) {
        ws.removeEventListener('message', onMsg);
        if (m.error) reject(new Error(JSON.stringify(m.error)));
        else resolve(m.result);
      }
    };
    ws.addEventListener('message', onMsg);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  if (cmd === 'tabs') {
    const targets = await listTargets();
    for (const t of targets) console.log(`${t.type}\t${t.id}\t${t.title}\t${t.url}`);
    return;
  }
  const targets = await listTargets();
  const pages = targets.filter(t => t.type === 'page');
  if (!pages.length) throw new Error('no page target');
  // Prefer our local static-server page, else the first page.
  const page = pages.find(t => t.url.includes('127.0.0.1:8792')) || pages[0];
  const ws = await connect(page.webSocketDebuggerUrl);
  try {
    await send(ws, 'Runtime.enable');
    if (cmd === 'nav') {
      await send(ws, 'Page.enable');
      await send(ws, 'Page.navigate', { url: args[0] });
      for (let i = 0; i < 100; i++) {
        await sleep(100);
        try {
          const r = await send(ws, 'Runtime.evaluate', { expression: 'document.readyState', returnByValue: true });
          if (r.result && r.result.value === 'complete') break;
        } catch { /* retry */ }
      }
      const r = await send(ws, 'Runtime.evaluate', { expression: '[document.title, location.href, document.body.scrollHeight, window.innerHeight, window.scrollY].join(" | ")', returnByValue: true });
      console.log('NAV OK -> ' + r.result.value);
    } else if (cmd === 'scroll') {
      const y = Number(args[0] || 0);
      const r = await send(ws, 'Runtime.evaluate', { expression: `window.scrollTo(0, ${y}); JSON.stringify([window.scrollY, document.body.scrollHeight, window.innerHeight])`, returnByValue: true });
      console.log('SCROLL -> ' + r.result.value);
    } else if (cmd === 'shot') {
      const r = await send(ws, 'Page.captureScreenshot', { format: 'png' });
      const fs = await import('node:fs');
      fs.writeFileSync(args[0], Buffer.from(r.data, 'base64'));
      console.log('SHOT saved ' + args[0] + ' bytes=' + Buffer.from(r.data, 'base64').length);
    } else if (cmd === 'eval') {
      const r = await send(ws, 'Runtime.evaluate', { expression: args[0], returnByValue: true, awaitPromise: true });
      console.log(JSON.stringify(r.result && r.result.value !== undefined ? r.result.value : r));
    } else {
      console.log('unknown cmd: ' + cmd);
      process.exitCode = 2;
    }
  } finally {
    try { ws.close(); } catch {}
  }
}

main().catch(e => { console.error('ERR: ' + e.message); process.exit(1); });
