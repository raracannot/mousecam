const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true});
  if (r.exceptionDetails) return 'EXC ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result?.value; };
console.log("set_app_settings:", await ev(`window.__TAURI__.core.invoke('set_app_settings',
  { capturesDir: 'E:\\\\RAYS\\\\Desktop\\\\workspace\\\\mousecam\\\\rust\\\\mc-engine\\\\captures', hw: true, hud: true })
  .then(r => 'OK ' + JSON.stringify(r)).catch(e => 'ERR ' + e)`));
console.log("app_settings:", await ev(`window.__TAURI__.core.invoke('app_settings')
  .then(r => JSON.stringify(r)).catch(e => 'ERR ' + e)`));
console.log("open_folder:", await ev(`window.__TAURI__.core.invoke('open_folder', { dir: 'E:\\\\RAYS\\\\Desktop\\\\workspace\\\\mousecam\\\\rust\\\\mc-engine\\\\captures' })
  .then(r => 'OK').catch(e => 'ERR ' + e)`));
ws.close();
