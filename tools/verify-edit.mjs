// Verifies timeline trimming, keyframe editing and proxy playback.
import fs from 'node:fs';
import path from 'node:path';

const port = process.argv[2] || '9222';
const outDir = process.argv[3] || 'shots';
const base = `http://127.0.0.1:${port}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForPage(timeoutMs = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const ts = await (await fetch(`${base}/json`)).json();
      const p = ts.find((t) => t.type === 'page' && !t.url.startsWith('devtools://'));
      if (p?.webSocketDebuggerUrl) return p;
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
      this.ws.onerror = () => rej(new Error('ws error'));
    });
    this.ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
      } else if (m.method) this.events.push(m);
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (this.pending.has(id)) { this.pending.delete(id); rej(new Error(`timeout ${method}`)); }
      }, 180000);
    });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' ' + (r.exceptionDetails.exception?.description || ''));
    return r.result.value;
  }
  async shot(f) {
    const r = await this.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(f, Buffer.from(r.data, 'base64'));
  }
  close() { try { this.ws.close(); } catch {} }
}

const results = [];
const check = (name, ok, d = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${d ? '  — ' + d : ''}`);
};

async function drag(cdp, x0, y0, x1, y1) {
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: x0, y: y0, button: 'left', buttons: 1, clickCount: 1 });
  await sleep(90);
  const steps = 6;
  for (let i = 1; i <= steps; i++) {
    await cdp.send('Input.dispatchMouseEvent', {
      type: 'mouseMoved',
      x: x0 + ((x1 - x0) * i) / steps,
      y: y0 + ((y1 - y0) * i) / steps,
      button: 'left',
      buttons: 1,
    });
    await sleep(60);
  }
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: x1, y: y1, button: 'left', buttons: 0, clickCount: 1 });
}

async function click(cdp, x, y) {
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await sleep(40);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
}

const rect = (cdp, id) => cdp.eval(`(() => { const r = document.getElementById('${id}').getBoundingClientRect();
  return JSON.stringify({x:r.left,y:r.top,w:r.width,h:r.height}); })()`).then(JSON.parse);

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const page = await waitForPage();
  const cdp = new CDP(page.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  for (let i = 0; i < 80; i++) {
    try {
      const t = await cdp.eval(`document.getElementById('frameInfo')?.textContent || ''`);
      if (t && t !== '—') break;
    } catch {}
    await sleep(250);
  }

  // start from defaults so the capture is representative
  await cdp.eval(`document.getElementById('btnReset').click()`);
  await sleep(900);

  // ---------- 1) trim by dragging ----------
  // A trim left by an earlier run puts its grips under the drag起点, and the
  // mousedown then edits that handle instead of starting a new range.
  await cdp.eval(`(() => { window.__mc.trim = null; })()`);
  await sleep(200);
  await cdp.eval(`(() => { const b = document.getElementById('trimToggle');
    if (!b.classList.contains('is-on')) b.click(); })()`);
  await sleep(200);
  const tl = await rect(cdp, 'tlCanvas');
  const ly = tl.y + tl.h * 0.62;
  await drag(cdp, tl.x + tl.w * 0.3, ly, tl.x + tl.w * 0.7, ly);
  await sleep(500);
  const trim = await cdp.eval(`JSON.stringify(window.__mc.trim)`);
  const chip = await cdp.eval(`document.getElementById('trimChip').style.display !== 'none'`);
  const t = JSON.parse(trim || 'null');
  check('拖拽创建裁切区间', !!t && t.b - t.a > 0.3, trim);
  check('裁切时长提示可见', chip);
  await cdp.shot(path.join(outDir, '47_trim.png'));

  // ---------- 2) keyframes ----------
  await cdp.eval(`(() => { const b = document.getElementById('kfToggle');
    if (!b.classList.contains('is-on')) b.click(); })()`);
  await sleep(200);
  const vc = await rect(cdp, 'viewCanvas');
  // two points inside the letterboxed image
  await click(cdp, vc.x + vc.w * 0.42, vc.y + vc.h * 0.45);
  await sleep(400);
  await click(cdp, vc.x + vc.w * 0.62, vc.y + vc.h * 0.55);
  await sleep(900);
  const kfs = await cdp.eval(`window.__mc.kfs.length`);
  check('创建跟随关键帧', kfs >= 2, `${kfs} 个`);
  await cdp.shot(path.join(outDir, '48_keyframes.png'));

  // ---------- 3) proxy ----------
  const hadProxy = await cdp.eval(`window.__mc.proxyReady`);
  if (!hadProxy) {
    await cdp.eval(`document.getElementById('btnProxy').click()`);
    for (let i = 0; i < 120; i++) {
      if (await cdp.eval(`window.__mc.proxyReady`)) break;
      await sleep(1000);
    }
  }
  const proxyOk = await cdp.eval(`window.__mc.proxyReady`);
  const videoOn = await cdp.eval(`document.getElementById('cropVideo').classList.contains('is-on')`);
  check('代理视频就绪', proxyOk === true);
  check('跟拍视口使用视频', videoOn === true);
  await cdp.shot(path.join(outDir, '49_proxy.png'));

  // ---------- 4) playback advances through the video ----------
  // Start a quarter into the clip: a short clip would otherwise finish before the
  // second sample and both readings would be the last frame.
  await cdp.eval(`(() => { const s = window.__mc; const fps = s.bake ? s.bake.fps : 30;
    const start = Math.floor((s.bake ? s.bake.frames : 60) * 0.25);
    s.frame = start;
    for (const el of [document.getElementById('viewVideo'), document.getElementById('cropVideo')]) {
      try { el.currentTime = start / fps; } catch {}
    } })()`);
  await sleep(350);
  await cdp.eval(`document.getElementById('btnPlay').click()`);
  await sleep(350);
  const f1 = await cdp.eval(`window.__mc.frame`);
  const ct = await cdp.eval(`document.getElementById('viewVideo').currentTime`);
  await sleep(700);
  const f2 = await cdp.eval(`window.__mc.frame`);
  await cdp.eval(`document.getElementById('btnPlay').click()`);
  check('播放推进帧号', f2 > f1, `${f1} -> ${f2}`);
  check('原片视频在播放', ct > 0, `currentTime=${Number(ct).toFixed(2)}s`);

  // ---------- 5) the export dialog offers the formats and drives the export ----------
  await cdp.eval(`document.getElementById('btnExport').click()`);
  await sleep(350);
  const dlg = await cdp.eval(`(() => {
    const m = document.getElementById('exportModal');
    return JSON.stringify({
      open: m && !m.classList.contains('is-hidden'),
      formats: [...document.getElementById('exFormat').options].map(o => o.value),
      hasQuality: !!document.getElementById('exQuality'),
      hasWidth: !!document.getElementById('exWidth'),
      hasFps: !!document.getElementById('exFps'),
    });
  })()`);
  const d = JSON.parse(dlg);
  check('导出弹窗可打开且有选项', d.open && d.formats.length === 6 && d.hasQuality && d.hasWidth && d.hasFps, dlg);
  await cdp.eval(`document.getElementById('exCancel').click()`);
  await sleep(200);
  check('弹窗可取消', await cdp.eval(`document.getElementById('exportModal').classList.contains('is-hidden')`));

  // ---------- 6) export respects the trim ----------
  const msg = await cdp.eval(`(async () => {
    const r = await window.__TAURI__.core.invoke('export', { dir: window.__mc.clip.dir, edit: (() => {
      const e = window.__mc.edit;
      const lines = ['zoom '+e.zoom,'expand '+e.expand,'threshold '+e.threshold,'smooth '+e.smooth,
                     'resp '+e.resp,'follow '+e.follow,'look '+e.look,'aspect '+e.aspect,'width '+e.width];
      if (window.__mc.trim) lines.push('trim '+window.__mc.trim.a.toFixed(3)+' '+window.__mc.trim.b.toFixed(3));
      return lines.join('\\n');
    })(), out: '', format: 'mp4_h264', quality: 18, width: 0, fps: 0 });
    return r;
  })()`);
  const m = String(msg).match(/([\d.]+)s\)/);
  const exported = m ? parseFloat(m[1]) : -1;
  const expected = t ? t.b - t.a : -1;
  check('导出时长等于裁切长度', Math.abs(exported - expected) < 0.35, `导出 ${exported}s / 裁切 ${expected.toFixed(2)}s`);

  // Leave the editor neutral: trim mode off, and no trim/keyframes pinning the
  // viewport, or the next suite's "changing a parameter moves the viewport"
  // check sees a rect that keyframes have frozen.
  await cdp.eval(`(() => {
    const b = document.getElementById('trimToggle');
    if (b.classList.contains('is-on')) b.click();
    const k = document.getElementById('kfToggle');
    if (k && k.classList.contains('is-on')) k.click();
    window.__mc.trim = null;
    window.__mc.kfs = [];
  })()`);
  await sleep(250);

  const errs = cdp.events.filter((e) => e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error');
  check('无 console 错误', errs.length === 0, `${errs.length}`);

  cdp.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error('VERIFY ERROR:', e.message); process.exit(2); });
