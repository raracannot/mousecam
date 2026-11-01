const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };

console.log("settings btn exists:", await ev(`!!document.getElementById('wbSettings')`));
await ev(`document.getElementById('wbSettings').click()`);
await new Promise(r => setTimeout(r, 900));
console.log("dialog open:", await ev(`!document.getElementById('settingsModal').classList.contains('is-hidden')`));
console.log("current:", await ev(`JSON.stringify({ effective: document.getElementById('setCapturesHint').textContent,
  hw: document.getElementById('setHw').checked, hud: document.getElementById('setHud').checked,
  configured: document.getElementById('setCaptures').value })`));
// point it inside the workspace so this sandbox can write
await ev(`(() => { document.getElementById('setCaptures').value = 'E:\\\\RAYS\\\\Desktop\\\\workspace\\\\mousecam\\\\rust\\\\mc-engine\\\\captures';
  document.getElementById('setSave').click(); })()`);
await new Promise(r => setTimeout(r, 2500));
console.log("after save:", await ev(`JSON.stringify(await window.__TAURI__.core.invoke('app_settings'))`));
ws.close();
