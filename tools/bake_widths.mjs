const clip = process.argv[2];
const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, params={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.exception?.description||'')); };
const edit = 'zoom 1.0\nexpand 1.2\nthreshold 3400\nsmooth 66\nresp 35\nfollow 1.0\nlook 60\naspect 0\nwidth 1080';
const raw = await ev(`window.__TAURI__.core.invoke('api_bake', { dir: ${JSON.stringify(clip)}, edit: ${JSON.stringify(edit)} }).then(v=>JSON.stringify({frames:v.frames,fps:v.fps,path:v.path})).catch(e=>'ERR '+e)`);
try {
  const b = JSON.parse(raw);
  const widths = b.path.map(q => q[2]);
  const peak = Math.max(...widths);
  console.log("frames:", b.frames, "fps:", b.fps);
  console.log("width min/max:", Math.min(...widths), "/", peak);
  console.log("growth at peak:", (peak / 1080).toFixed(3));
  const step = Math.max(1, Math.floor(widths.length / 14));
  console.log("widths over time:", widths.filter((_, i) => i % step === 0).join(", "));
} catch { console.log(raw.slice(0, 300)); }
ws.close();
