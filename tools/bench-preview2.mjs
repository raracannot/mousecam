const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value; };

console.log("img:", await ev(`(() => { const i = document.getElementById('recPreview');
  return JSON.stringify({ src: i.src.slice(-40), nw: i.naturalWidth, nh: i.naturalHeight, complete: i.complete }); })()`));

const bench = await ev(`(async () => {
  const t = { path: [], data: [] };
  for (let i = 0; i < 20; i++) {
    let a = performance.now(); await window.__TAURI__.core.invoke('preview_frame_path'); t.path.push(performance.now() - a);
    a = performance.now(); await window.__TAURI__.core.invoke('preview_frame'); t.data.push(performance.now() - a);
    await new Promise(r => setTimeout(r, 20));
  }
  const med = (x) => x.sort((a,b)=>a-b)[Math.floor(x.length/2)];
  return JSON.stringify({ path_ms: +med(t.path).toFixed(1), data_ms: +med(t.data).toFixed(1) });
})()`);
console.log("round trip:", bench);
ws.close();
