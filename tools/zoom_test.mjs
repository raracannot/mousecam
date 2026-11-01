const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value; };

const setZoom = async (v) => ev(`(() => {
  const row = [...document.querySelectorAll('#recParamsGrid .row')]
    .find(r => r.querySelector('.row-label').textContent.includes('视口缩放'));
  if (!row) return 'no row';
  const inp = row.querySelector('input[type=range]');
  inp.value = ${v};
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  return inp.value;
})()`);

for (const z of [1.0, 2.0, 0.6]) {
  const ok = await setZoom(z);
  await new Promise(r => setTimeout(r, 1200));
  const chip = await ev(`document.getElementById('recCropInfo').textContent`);
  console.log(`zoom=${z} -> set ${ok}, preview chip ${chip}`);
}
// repeated toggles: the race trigger
for (let i = 0; i < 3; i++) {
  await ev(`document.getElementById('hudToggle').click()`);
  await new Promise(r => setTimeout(r, 300));
  await ev(`document.getElementById('hudToggle').click()`);
  await new Promise(r => setTimeout(r, 500));
}
console.log("chip after toggles:", await ev(`document.getElementById('recCropInfo').textContent`));
ws.close();
