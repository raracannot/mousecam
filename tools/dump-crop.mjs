import fs from "node:fs";
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
await new Promise(r => setTimeout(r, 2200));
// park on a frame slow enough to be drawn from the video
await ev(`(() => { const s = window.__mc; s.proxyReady = false; s.proxyStale = true;
  s.frame = Math.floor(s.bake.frames * 0.5); drawLeft(); drawRight(); })()`);
await new Promise(r => setTimeout(r, 700));
const info = await ev(`JSON.stringify({ frame: window.__mc.frame, path: window.__mc.bake.path[window.__mc.frame],
  mon: window.__mc.bake.mon, fps: window.__mc.bake.fps, dir: window.__mc.clip.dir })`);
const url = await ev(`document.getElementById('cropCanvas').toDataURL('image/png')`);
fs.writeFileSync("E:\\RAYS\\Desktop\\workspace\\mousecam\\shots\\99_crop_canvas.png", Buffer.from(url.split(',')[1], 'base64'));
fs.writeFileSync("E:\\RAYS\\Desktop\\workspace\\mousecam\\shots\\99_crop_info.json", info);
console.log(info);
ws.close();
