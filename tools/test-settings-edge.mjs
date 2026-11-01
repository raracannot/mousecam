const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };
const call = (cmd, args) => ev(`window.__TAURI__.core.invoke(${JSON.stringify(cmd)}, ${JSON.stringify(args)}).then(r=>'OK '+JSON.stringify(r)).catch(e=>'ERR '+e)`);

console.log("1) empty captures (expect default):");
console.log("   set  ", await call('set_app_settings', { capturesDir: '', hw: true, hud: true, verbose: true }));
console.log("   get  ", await call('app_settings'));

console.log("2) path with spaces:");
console.log("   set  ", await call('set_app_settings', { capturesDir: 'E:\\RAYS\\Desktop\\workspace\\mousecam\\rust\\mc-engine\\test captures', hw: true, hud: true, verbose: true }));
console.log("   get  ", await call('app_settings'));

console.log("3) trailing backslash + spaces:");
console.log("   set  ", await call('set_app_settings', { capturesDir: '  E:\\RAYS\\Desktop\\workspace\\mousecam\\rust\\mc-engine\\captures\\  ', hw: true, hud: true, verbose: true }));
console.log("   get  ", await call('app_settings'));

console.log("4) restore:");
console.log("   set  ", await call('set_app_settings', { capturesDir: 'E:\\RAYS\\Desktop\\workspace\\mousecam\\rust\\mc-engine\\captures', hw: true, hud: true, verbose: true }));
ws.close();
