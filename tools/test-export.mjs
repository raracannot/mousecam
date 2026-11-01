const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };
const clip = await ev(`window.__mc.clips[0].dir`);
console.log("clip:", clip, "| dur:", await ev(`window.__mc.clips[0].duration`));
// export through the real command, mp4 h264
const out = "E:\\RAYS\\Desktop\\workspace\\mousecam\\shots\\98_export_test.mp4";
console.log("export:", await ev(`window.__TAURI__.core.invoke('export', { dir: ${JSON.stringify(clip)}, edit: '', out: ${JSON.stringify(out)}, format: 'mp4_h264', quality: 20, width: 1280, fps: 30 }).then(r=>'OK '+r).catch(e=>'ERR '+e)`));
ws.close();
