const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };
await ev(`document.querySelector('.tab[data-tab="edit"]').click()`);
await new Promise(r => setTimeout(r, 2000));
console.log("before:", await ev(`JSON.stringify({ playing: window.__mc.playing, useVideo: window.__mc.useVideo, frame: window.__mc.frame,
  paused: document.getElementById('viewVideo').paused, ct: +document.getElementById('viewVideo').currentTime.toFixed(2), rs: document.getElementById('viewVideo').readyState })`));
await ev(`document.getElementById('btnPlay').click()`);
for (const t of [400, 900, 1500]) {
  await new Promise(r => setTimeout(r, t));
  console.log(t + "ms:", await ev(`JSON.stringify({ playing: window.__mc.playing, frame: window.__mc.frame,
    paused: document.getElementById('viewVideo').paused, ct: +document.getElementById('viewVideo').currentTime.toFixed(2) })`));
}
await ev(`document.getElementById('btnPlay').click()`);
ws.close();
