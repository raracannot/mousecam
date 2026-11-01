const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map(); const errs = [];
ws.onmessage = e => { const m = JSON.parse(e.data);
  if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); }
  else if (m.method === "Runtime.exceptionThrown") errs.push(m.params.exceptionDetails.text); };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
await send("Runtime.enable");
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const ok = (name, cond, extra='') => console.log((cond ? 'PASS  ' : 'FAIL  ') + name + (extra ? '  — ' + extra : ''));

ok('boot', await ev(`typeof window.__mc === 'object'`));
ok('clips listed', Number(await ev(`window.__mc.clips.length`)) > 0, String(await ev(`window.__mc.clips.length`)));
ok('settings loaded', (await ev(`JSON.stringify(window.__mc.appSettings)`)) !== 'null');

// record page
await ev(`document.querySelector('.tab[data-tab="record"]').click()`);
await sleep(2500);
ok('preview frame arrives', await ev(`!!document.getElementById('recPreview').src`));

// hud toggle off/on
await ev(`document.getElementById('hudToggle').click()`);
await sleep(600);
const off = await ev(`document.getElementById('hudToggle').className`);
await ev(`document.getElementById('hudToggle').click()`);
await sleep(600);
const on = await ev(`document.getElementById('hudToggle').className`);
ok('hud toggle cycles', !off.includes('is-on') && on.includes('is-on'), off + ' -> ' + on);

// settings round trip
await ev(`document.getElementById('wbSettings').click()`);
await sleep(700);
const before = await ev(`document.getElementById('setCaptures').value`);
await ev(`document.getElementById('setCaptures').value = 'E:\\\\RAYS\\\\Desktop\\\\workspace\\\\mousecam\\\\rust\\\\mc-engine\\\\captures'`);
await ev(`document.getElementById('setSave').click()`);
await sleep(2000);
const after = await ev(`JSON.stringify(window.__mc.appSettings)`);
ok('settings save persists', after.includes('mc-engine'), after.slice(0, 90));
ok('dialog closed after save', await ev(`document.getElementById('settingsModal').classList.contains('is-hidden')`));

// back to edit page, check follow view draws from video
await ev(`document.querySelector('.tab[data-tab="edit"]').click()`);
await sleep(2200);
await ev(`(() => { window.__mc.proxyReady = false; window.__mc.proxyStale = true; })()`);
await sleep(500);
const bytes1 = await ev(`document.getElementById('cropCanvas').toDataURL().length`);
await ev(`document.getElementById('btnPlay').click()`);
await sleep(1200);
const bytes2 = await ev(`document.getElementById('cropCanvas').toDataURL().length`);
await ev(`document.getElementById('btnPlay').click()`);
ok('follow view updates during playback', bytes1 !== bytes2, bytes1 + ' -> ' + bytes2);
ok('no page exceptions', errs.length === 0, errs.join(' | '));
ws.close();
