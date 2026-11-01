const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };
console.log("monitors:", await ev(`JSON.stringify(window.__mc.mons || [])`));
console.log("current value:", await ev(`document.getElementById('recMonitor').value`));
// switch to the second display
await ev(`(() => { const s = document.getElementById('recMonitor'); s.value = '1';
  s.dispatchEvent(new Event('change', { bubbles: true })); })()`);
await new Promise(r => setTimeout(r, 3000));
console.log("after switch:", await ev(`document.getElementById('recMonitor').value + ' | ' + document.getElementById('recCropInfo').textContent`));
ws.close();
