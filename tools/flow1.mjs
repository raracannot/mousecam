const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, params={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.exception?.description||'')); };

// record page, HUD on
await ev(`document.querySelector('.tab[data-tab="record"]').click()`);
await new Promise(r => setTimeout(r, 2000));
await ev(`document.getElementById('hudToggle').classList.contains('is-on') || document.getElementById('hudToggle').click()`);
await new Promise(r => setTimeout(r, 900));
console.log("on record page: toggle =", await ev(`document.getElementById('hudToggle').className`), "| engine =", await ev(`window.__TAURI__.core.invoke('hud_get')`));
console.log("window visible:", await ev(`'see next output'`));
ws.close();
