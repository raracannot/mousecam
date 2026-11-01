// CDP-based UI verification: drives the running demo and captures evidence.
// Usage: node tools/verify.mjs <port> <outDir>
import fs from 'node:fs';
import path from 'node:path';

const port = process.argv[2] || '9222';
const outDir = process.argv[3] || 'shots';
const target = `http://127.0.0.1:${port}`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function listTargets() {
  const r = await fetch(`${target}/json`);
  return r.json();
}

async function waitForPage(timeoutMs = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const ts = await listTargets();
      const page = ts.find((t) => t.type === 'page' && !t.url.startsWith('devtools://'));
      if (page && page.webSocketDebuggerUrl) return page;
    } catch {}
    await sleep(300);
  }
  throw new Error('CDP target not found');
}

class CDP {
  constructor(url) {
    this.ws = new WebSocket(url);
    this.id = 0;
    this.pending = new Map();
    this.events = [];
    this.ready = new Promise((res, rej) => {
      this.ws.onopen = () => res();
      this.ws.onerror = (e) => rej(new Error('ws error'));
    });
    this.ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { res, rej } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
      } else if (msg.method) {
        this.events.push(msg);
      }
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          rej(new Error(`timeout: ${method}`));
        }
      }, 30000);
    });
  }
  async eval(expr) {
    const r = await this.send('Runtime.evaluate', {
      expression: expr,
      returnByValue: true,
      awaitPromise: true,
    });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' ' + (r.exceptionDetails.exception?.description || ''));
    return r.result.value;
  }
  async shot(file) {
    const r = await this.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
    return file;
  }
  close() {
    try { this.ws.close(); } catch {}
  }
}

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`);
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const page = await waitForPage();
  console.log('target:', page.url);

  const cdp = new CDP(page.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  // start from a known tab: a previous suite may have left the recorder open
  await cdp.eval(`document.querySelector('.tab[data-tab="edit"]').click()`);
  await sleep(600);
  // Normalise the editor before measuring anything: a trim or a keyframe left
  // by another suite puts grips under the clicks and silently swallows them.
  await cdp.eval(`(() => {
    const t = document.getElementById('trimToggle');
    if (t && t.classList.contains('is-on')) t.click();
    const k = document.getElementById('kfToggle');
    if (k && k.classList.contains('is-on')) k.click();
    window.__mc.trim = null;
    window.__mc.kfs = [];
    window.__mc.frame = 0;
    window.__mc.zoom = 0;
    document.querySelectorAll('#tlZoom button')[0]?.click();
  })()`);
  await sleep(300);

  // 裁切模式下点击时间线是画区间，不是定位；确保它关掉
  await cdp.eval(`(() => { const b = document.getElementById('trimToggle');
    if (b.classList.contains('is-on')) b.click(); })()`);
  await sleep(200);


  // ---- wait until the clip is loaded and the first still is painted
  let ready = false;
  for (let i = 0; i < 80; i++) {
    try {
      const txt = await cdp.eval(`document.getElementById('frameInfo')?.textContent || ''`);
      if (txt && txt !== '—') { ready = true; break; }
    } catch {}
    await sleep(250);
  }
  check('素材载入并绘制', ready);

  const info = await cdp.eval(`JSON.stringify({
    mon: document.getElementById('monInfo').textContent,
    total: document.getElementById('tcTotal').textContent,
    frame: document.getElementById('frameInfo').textContent,
    crop: document.getElementById('cropInfo').textContent
  })`);
  console.log('state:', info);

  const clipOpts = await cdp.eval(`document.getElementById('clipSel').options.length`);
  check('素材选择器已填充', clipOpts > 0, `${clipOpts} 个素材`);

  await sleep(600);
  await cdp.shot(path.join(outDir, '41_ui_initial.png'));

  // ---- interaction 1: click the timeline at 60%
  const box = await cdp.eval(`(() => { const r = document.getElementById('tlCanvas').getBoundingClientRect();
    return JSON.stringify({x: r.left, y: r.top, w: r.width, h: r.height}); })()`);
  const b = JSON.parse(box);
  const cx = b.x + b.w * 0.6;
  const cy = b.y + b.h * 0.55;
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: cx, y: cy, button: 'left', clickCount: 1 });
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: cx, y: cy, button: 'left', clickCount: 1 });
  await sleep(1200);
  const afterSeek = await cdp.eval(`document.getElementById('tcNow').textContent`);
  check('时间线点击可定位', afterSeek !== '00:00.00', `tcNow=${afterSeek}`);
  await cdp.shot(path.join(outDir, '42_ui_seek.png'));

  // ---- interaction 2: change zoom and confirm the viewport reacts
  const beforeCrop = await cdp.eval(`document.getElementById('cropInfo').textContent`);
  await cdp.eval(`(() => {
    const inp = document.querySelectorAll('.params-grid input[type=range]')[0];
    inp.value = 2.2;
    inp.dispatchEvent(new Event('input', {bubbles:true}));
    return inp.value;
  })()`);
  await sleep(1500);
  const afterCrop = await cdp.eval(`document.getElementById('cropInfo').textContent`);
  check('改参数后视口实时重算', beforeCrop !== afterCrop, `${beforeCrop} -> ${afterCrop}`);
  await cdp.shot(path.join(outDir, '43_ui_zoom.png'));

  // ---- interaction 3: both viewports actually have pixels
  const painted = await cdp.eval(`(() => {
    const f = (id) => {
      const c = document.getElementById(id);
      const g = c.getContext('2d');
      const d = g.getImageData(0, 0, c.width, c.height).data;
      let sum = 0, n = 0;
      for (let i = 0; i < d.length; i += 4000) { sum += d[i]; n++; }
      return sum / n;
    };
    return JSON.stringify({ view: f('viewCanvas'), crop: f('cropCanvas') });
  })()`);
  const p = JSON.parse(painted);
  check('左视口有内容', p.view > 1, `avg=${p.view.toFixed(1)}`);
  check('右视口有内容', p.crop > 1, `avg=${p.crop.toFixed(1)}`);

  // ---- console errors
  const errs = cdp.events.filter((e) => e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error');
  check('无 console 错误', errs.length === 0, `${errs.length} errors`);

  cdp.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error('VERIFY ERROR:', e.message);
  process.exit(2);
});
