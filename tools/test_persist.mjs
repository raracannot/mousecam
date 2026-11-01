const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, params={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.exception?.description||'')); };

await ev(`localStorage.removeItem('mc.params'); location.reload()`);
await new Promise(r => setTimeout(r, 2500));
console.log("defaults:", await ev(`JSON.stringify(window.__mc.edit)`));

// change several values through the real controls
await ev(`(() => {
  const rows = [...document.querySelectorAll('#recParamsGrid .row')];
  const zoomRow = rows.find(r => r.querySelector('.row-label').textContent.includes('视口缩放'));
  const inp = zoomRow.querySelector('input[type=range]');
  inp.value = '2.35'; inp.dispatchEvent(new Event('input', { bubbles: true }));
  const sel = [...document.querySelectorAll('#recParamsGrid select')][0];
  sel.value = '1920'; sel.dispatchEvent(new Event('change', { bubbles: true }));
  const w = document.getElementById('hudWidth');
  w.value = '4'; w.dispatchEvent(new Event('input', { bubbles: true }));
  const lab = document.getElementById('hudLabel');
  lab.checked = false; lab.dispatchEvent(new Event('change', { bubbles: true }));
})()`);
await new Promise(r => setTimeout(r, 600));
console.log("after edit:", await ev(`JSON.stringify({ edit: window.__mc.edit, saved: localStorage.getItem('mc.params') })`));

await ev(`location.reload()`);
await new Promise(r => setTimeout(r, 2800));
console.log("after reload:", await ev(`JSON.stringify({ edit: window.__mc.edit, hudWidth: document.getElementById('hudWidth').value, hudLabel: document.getElementById('hudLabel').checked })`));
console.log("zoom text in grid:", await ev(`(() => {
  const rows = [...document.querySelectorAll('#recParamsGrid .row')];
  const zoomRow = rows.find(r => r.querySelector('.row-label').textContent.includes('视口缩放'));
  const wRow = rows.find(r => r.querySelector('.row-label').textContent.includes('宽度'));
  return JSON.stringify({ zoom: zoomRow.querySelector('.row-val').textContent, width: wRow.querySelector('select').value });
})()`));
ws.close();
