const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + JSON.stringify(r.exceptionDetails?.exception?.description||'')); };

const row = (grid, label) => `[...document.querySelectorAll('#${grid} .row')].find(r => r.querySelector('.row-label').textContent.includes('${label}'))`;

// 1. double-click opens an input
console.log("dblclick opens editor:", await ev(`(() => {
  const r = ${row('recParamsGrid','视口缩放')};
  r.querySelector('.row-val').dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
  const ed = r.querySelector('.row-val-edit');
  return ed ? 'YES value=' + ed.value + ' focused=' + (document.activeElement === ed) : 'NO';
})()`));

// 2. type a value and press Enter
console.log("enter 2.35 ->", await ev(`(() => {
  const r = ${row('recParamsGrid','视口缩放')};
  const ed = r.querySelector('.row-val-edit');
  ed.value = '2.35';
  ed.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  return JSON.stringify({ text: r.querySelector('.row-val').textContent, slider: r.querySelector('input[type=range]').value });
})()`));

// 3. out-of-range clamps
console.log("enter 9 ->", await ev(`(() => {
  const r = ${row('recParamsGrid','视口缩放')};
  r.querySelector('.row-val').dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
  const ed = r.querySelector('.row-val-edit');
  ed.value = '9';
  ed.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  return JSON.stringify({ text: r.querySelector('.row-val').textContent, slider: r.querySelector('input[type=range]').value });
})()`));

// 4. Escape cancels
console.log("escape keeps value ->", await ev(`(() => {
  const r = ${row('recParamsGrid','视口缩放')};
  const before = r.querySelector('.row-val').textContent;
  r.querySelector('.row-val').dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
  const ed = r.querySelector('.row-val-edit');
  ed.value = '0.51';
  ed.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  return JSON.stringify({ before, after: r.querySelector('.row-val').textContent });
})()`));

// 5. typing must not reach the global hotkeys
console.log("keydown stopped before window:", await ev(`(() => {
  const r = ${row('recParamsGrid','视口缩放')};
  r.querySelector('.row-val').dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
  const ed = r.querySelector('.row-val-edit');
  let leaked = false;
  const spy = (e) => { if (e.target !== ed) leaked = true; };
  window.addEventListener('keydown', spy);
  ed.dispatchEvent(new KeyboardEvent('keydown', { key: 'F9', bubbles: true }));
  window.removeEventListener('keydown', spy);
  return leaked ? 'LEAKED' : 'kept out of the global handler';
})()`));
ws.close();
