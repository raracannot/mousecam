const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };
// 1) a JS exception thrown at top level
await ev(`setTimeout(() => { throw new Error('deliberate JS test error'); }, 10)`);
await new Promise(r => setTimeout(r, 600));
// 2) an unhandled promise rejection
await ev(`Promise.reject(new Error('deliberate rejection'))`);
await new Promise(r => setTimeout(r, 600));
// 3) a Rust panic on a worker thread
console.log("panic call:", await ev(`window.__TAURI__.core.invoke('debug_panic').then(r=>'ok').catch(e=>'caught: '+e)`));
await new Promise(r => setTimeout(r, 900));
// 4) a failing command is traced too
console.log("bad call:", await ev(`window.__TAURI__.core.invoke('still', { dir:'C:/nope', edit:'', frame:0, maxW:100, kind:'full' }).then(r=>'ok').catch(e=>'err')`));
await new Promise(r => setTimeout(r, 800));
ws.close();
