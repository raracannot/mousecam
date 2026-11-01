const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };

await ev(`document.querySelector('.tab[data-tab="record"]').click()`);
await new Promise(r => setTimeout(r, 3500));   // let the preview warm up

const stats = await ev(`(async () => {
  const t = [];
  for (let i = 0; i < 25; i++) {
    const a = performance.now();
    await window.__TAURI__.core.invoke('preview_frame');
    t.push(performance.now() - a);
    await new Promise(r => setTimeout(r, 30));
  }
  t.sort((x, y) => x - y);
  const pick = (q) => t[Math.min(t.length - 1, Math.floor(t.length * q))];
  return JSON.stringify({ median: +pick(0.5).toFixed(1), p90: +pick(0.9).toFixed(1), max: +t[t.length-1].toFixed(1), n: t.length });
})()`);
console.log(process.argv[2] + " | preview_frame round trip ms: " + stats);

// also: how often does the <img> actually change over 2 s while idle?
const fps = await ev(`(async () => {
  const img = document.getElementById('recPreview');
  let changes = 0, last = img.src.length;
  const t0 = performance.now();
  while (performance.now() - t0 < 2000) {
    await new Promise(r => setTimeout(r, 20));
    if (img.src !== img.dataset.last) { img.dataset.last = img.dataset.last; }
    const cur = img.src.length + '|' + (img.complete ? 1 : 0);
    if (cur !== last) { changes++; last = cur; }
  }
  return changes;
})()`);
console.log(process.argv[2] + " | preview updates in 2s: " + fps);
ws.close();
