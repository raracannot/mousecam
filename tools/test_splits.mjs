const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.exception?.description||'')); };

console.log("handles present:", await ev(`JSON.stringify(['splitVp','splitStageA','splitStageB'].map(i => !!document.getElementById(i)))`));
console.log("stage rows:", await ev(`getComputedStyle(document.getElementById('stageEdit')).gridTemplateRows`));
console.log("vp columns:", await ev(`getComputedStyle(document.querySelector('.viewports')).gridTemplateColumns`));

// simulate dragging the timeline handle upward by 40px
console.log("drag timeline handle:", await ev(`(() => {
  const h = document.getElementById('splitStageA');
  const r = h.getBoundingClientRect();
  const before = getComputedStyle(document.getElementById('stageEdit')).getPropertyValue('--tl-h') || 'default';
  const mk = (t, y) => new PointerEvent(t, { bubbles: true, clientX: r.left + r.width/2, clientY: y, pointerId: 1, pointerType: 'mouse', isPrimary: true });
  h.dispatchEvent(mk('pointerdown', r.top + 2));
  h.dispatchEvent(mk('pointermove', r.top - 38));
  h.dispatchEvent(mk('pointerup', r.top - 38));
  const after = document.getElementById('stageEdit').style.getPropertyValue('--tl-h');
  return JSON.stringify({ before, after });
})()`));

// simulate dragging the vertical handle to the right by 120px
console.log("drag column handle:", await ev(`(() => {
  const h = document.getElementById('splitVp');
  const r = h.getBoundingClientRect();
  const mk = (t, x) => new PointerEvent(t, { bubbles: true, clientX: x, clientY: r.top + r.height/2, pointerId: 2, pointerType: 'mouse', isPrimary: true });
  h.dispatchEvent(mk('pointerdown', r.left + 3));
  h.dispatchEvent(mk('pointermove', r.left + 123));
  h.dispatchEvent(mk('pointerup', r.left + 123));
  return document.querySelector('.viewports').style.getPropertyValue('--vp-left');
})()`));

console.log("persisted:", await ev(`localStorage.getItem('mc.split')`));
console.log("no console errors:", await ev(`'ok'`));
ws.close();
