// Is the UI thread still answering after the window was moved?
const base = 'http://127.0.0.1:9222';

async function probe(label) {
  try {
    const ts = await (await fetch(`${base}/json`, { signal: AbortSignal.timeout(3000) })).json();
    const p = ts.find((t) => t.type === 'page' && !t.url.startsWith('devtools://'));
    if (!p) return console.log(label, '-> no page');
    const ws = new WebSocket(p.webSocketDebuggerUrl);
    await new Promise((res, rej) => {
      ws.onopen = res;
      setTimeout(() => rej(new Error('ws open timeout')), 3000);
    });
    let id = 0;
    const pend = new Map();
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); }
    };
    const send = (method, params = {}) =>
      new Promise((r) => {
        const i = ++id;
        pend.set(i, r);
        ws.send(JSON.stringify({ id: i, method, params }));
        setTimeout(() => { if (pend.has(i)) { pend.delete(i); r(null); } }, 3000);
      });
    const r = await send('Runtime.evaluate', { expression: 'performance.now()', returnByValue: true });
    ws.close();
    console.log(label, r && r.result && r.result.value !== undefined ? '-> RESPONSIVE' : '-> TIMEOUT (frozen)');
  } catch (e) {
    console.log(label, '-> UNREACHABLE:', e.message);
  }
}

await probe('ui');
