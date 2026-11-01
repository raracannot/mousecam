const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, params={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true }); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.exception?.description||'')); };

// go to the recorder page
await ev(`document.querySelector('.tab[data-tab="record"]').click()`);
await new Promise(r => setTimeout(r, 2500));
console.log("record rows:", await ev(`getComputedStyle(document.getElementById('stageRecord')).gridTemplateRows`));
console.log("rec children:", await ev(`JSON.stringify([...document.getElementById('stageRecord').children].map(c => c.className.split(' ')[0] + '|' + Math.round(c.getBoundingClientRect().height)))`));
console.log("preview img:", await ev(`(() => { const i = document.getElementById('recPreview'); return JSON.stringify({nw:i.naturalWidth, nh:i.naturalHeight}); })()`));

// HUD on
await ev(`document.getElementById('hudToggle').click()`);
await new Promise(r => setTimeout(r, 900));
console.log("hud toggle after on:", await ev(`document.getElementById('hudToggle').className`));

// drag the recorder params handle
console.log("drag rec params:", await ev(`(() => {
  const h = document.getElementById('splitRecParams');
  const r = h.getBoundingClientRect();
  const mk = (t, y) => new PointerEvent(t, { bubbles: true, clientX: r.left + r.width/2, clientY: y, pointerId: 7, pointerType: 'mouse', isPrimary: true });
  h.dispatchEvent(mk('pointerdown', r.top + 2));
  h.dispatchEvent(mk('pointermove', r.top - 60));
  h.dispatchEvent(mk('pointerup', r.top - 60));
  return document.getElementById('stageRecord').style.getPropertyValue('--rec-params-h');
})()`));

// switch to the editor: the frame must switch itself off
await ev(`document.querySelector('.tab[data-tab="edit"]').click()`);
await new Promise(r => setTimeout(r, 1200));
console.log("hud toggle after leaving record:", await ev(`document.getElementById('hudToggle').className`));
console.log("hud enabled in engine:", await ev(`window.__TAURI__.core.invoke('hud_get')`));
ws.close();
