// Verifies the recorder page: live preview, parameter feedback, record cycle.
import fs from 'node:fs';
const port = process.argv[2] || '9222';
const outDir = process.argv[3] || 'shots';
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForPage(t = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < t) {
    try {
      const ts = await (await fetch(`${base}/json`)).json();
      const p = ts.find((x) => x.type === 'page' && !x.url.startsWith('devtools://'));
      if (p?.webSocketDebuggerUrl) return p;
    } catch {}
    await sleep(300);
  }
  throw new Error('no CDP target');
}
class CDP {
  constructor(u) {
    this.ws = new WebSocket(u); this.id = 0; this.pending = new Map(); this.events = [];
    this.ready = new Promise((res, rej) => { this.ws.onopen = () => res(); this.ws.onerror = () => rej(new Error('ws')); });
    this.ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.id && this.pending.has(m.id)) { const { res, rej } = this.pending.get(m.id); this.pending.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
      else if (m.method) this.events.push(m);
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => { this.pending.set(id, { res, rej }); this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); rej(new Error('timeout ' + method)); } }, 120000); });
  }
  async eval(e) { const r = await this.send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.text); return r.result.value; }
  async shot(f) { const r = await this.send('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(f, Buffer.from(r.data, 'base64')); }
  close() { try { this.ws.close(); } catch {} }
}
const results = [];
const check = (n, ok, d = '') => { results.push({ n, ok }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + d : ''}`); };

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const page = await waitForPage();
  const cdp = new CDP(page.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  for (let i = 0; i < 80; i++) {
    try { const t = await cdp.eval(`document.getElementById('frameInfo')?.textContent || ''`); if (t && t !== '—') break; } catch {}
    await sleep(250);
  }

  await cdp.eval(`document.querySelector('.tab[data-tab="record"]').click()`);
  await sleep(1500);

  let live = false;
  for (let i = 0; i < 60; i++) {
    live = await cdp.eval(`(() => { const im = document.getElementById('recPreview');
      return !!(im.src && im.src.startsWith('data:image') && im.naturalWidth > 0); })()`);
    if (live) break;
    await sleep(300);
  }
  check('跟拍实时预览出图', live);

  const size1 = await cdp.eval(`document.getElementById('recCropInfo').textContent`);
  check('预览尺寸标注', /^\d+×\d+$/.test(size1 || ''), size1);
  await cdp.shot(outDir + '/50_record_preview.png');

  // parameter feedback: zoom changes the crop size
  await cdp.eval(`(() => { const inp = document.getElementById('recParamsGrid').querySelectorAll('input[type=range]')[0];
    inp.value = 2.4; inp.dispatchEvent(new Event('input', { bubbles: true })); })()`);
  await sleep(1600);
  const size2 = await cdp.eval(`document.getElementById('recCropInfo').textContent`);
  check('参数实时影响预览', size1 !== size2, `${size1} -> ${size2}`);

  // record cycle inside the recorder page
  await cdp.eval(`document.getElementById('recOrb').click()`);
  await sleep(1500);
  const st = await cdp.eval(`document.getElementById('recState').textContent`);
  check('进入录制状态', st === '录制中', st);
  await sleep(2500);
  const t = await cdp.eval(`document.getElementById('recTime').textContent`);
  check('计时器在走', t !== '00:00.0', t);
  const stillLive = await cdp.eval(`(() => { const im = document.getElementById('recPreview');
    return !!(im.src && im.src.startsWith('data:image') && im.naturalWidth > 0); })()`);
  check('录制中预览继续工作', stillLive);
  await cdp.shot(outDir + '/51_recording_with_preview.png');

  await cdp.eval(`document.getElementById('recOrb').click()`);
  for (let i = 0; i < 60; i++) {
    if ((await cdp.eval(`document.getElementById('recState').textContent`)) !== '录制中') break;
    await sleep(500);
  }
  await sleep(1200);
  check('停止后回到待机', (await cdp.eval(`document.getElementById('recState').textContent`)) === '待机');

  const errs = cdp.events.filter((e) => e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error');
  check('无 console 错误', errs.length === 0, `${errs.length}`);

  cdp.close();
  const bad = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - bad}/${results.length} checks passed`);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error('VERIFY ERROR:', e.message); process.exit(2); });
