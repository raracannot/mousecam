const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value; };
for (let i = 1; i <= 5; i++) {
  await ev(`document.getElementById('hudToggle').click()`);   // off
  await new Promise(r => setTimeout(r, 400));
  const off = await ev(`document.getElementById('hudToggle').className`);
  await ev(`document.getElementById('hudToggle').click()`);   // on
  await new Promise(r => setTimeout(r, 600));
  const on = await ev(`document.getElementById('hudToggle').className`);
  console.log(`cycle ${i}: after off -> "${off}" | after on -> "${on}"`);
}
ws.close();
