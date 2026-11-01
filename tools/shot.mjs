import fs from 'node:fs';
const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, params={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params})); });
// put the split back to a sane starting point for the picture
await send("Runtime.evaluate", { expression: "localStorage.removeItem('mc.split'); location.reload();" });
await new Promise(r => setTimeout(r, 2500));
const shot = await send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync(process.argv[2], Buffer.from(shot.data, "base64"));
console.log("screenshot saved");
ws.close();
