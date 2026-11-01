// Timeline regression checks.
// The important detail: click positions are derived from the VISIBLE CARD,
// never from the canvas rect. Deriving both from the canvas is what made the
// earlier test pass while the mapping was actually wrong by 4x.
import fs from 'node:fs';

const port = process.argv[2] || '9222';
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
    this.ws = new WebSocket(u); this.id = 0; this.pending = new Map();
    this.ready = new Promise((res, rej) => { this.ws.onopen = () => res(); this.ws.onerror = () => rej(new Error('ws')); });
    this.ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.id && this.pending.has(m.id)) { const { res, rej } = this.pending.get(m.id); this.pending.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      this.pending.set(id, { res, rej });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => { if (this.pending.has(id)) { this.pending.delete(id); rej(new Error('timeout ' + method)); } }, 60000);
    });
  }
  async eval(e) {
    const r = await this.send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text);
    return r.result.value;
  }
  close() { try { this.ws.close(); } catch {} }
}
const results = [];
const check = (n, ok, d = '') => { results.push({ n, ok }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${n}${d ? '  — ' + d : ''}`); };

async function click(cdp, x, y) {
  await cdp.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await sleep(40);
  await cdp.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
}

const GEOM = `(() => {
  const cv = document.getElementById('tlCanvas');
  const card = document.querySelector('.timeline');
  const c = cv.getBoundingClientRect();
  const k = card.getBoundingClientRect();
  return JSON.stringify({ cvW: Math.round(c.width), cvH: Math.round(c.height),
    cardW: Math.round(k.width), cardH: Math.round(k.height),
    cardLeft: k.left, cardTop: k.top });
})()`;

(async () => {
  const page = await waitForPage();
  const cdp = new CDP(page.webSocketDebuggerUrl);
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');

  for (let i = 0; i < 80; i++) {
    try { const t = await cdp.eval(`document.getElementById('frameInfo')?.textContent || ''`); if (t && t !== '—') break; } catch {}
    await sleep(250);
  }
  await cdp.eval(`document.querySelector('.tab[data-tab="edit"]').click()`);
  await sleep(800);
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


  // ---------- 1) canvas must not exceed its card
  let g = JSON.parse(await cdp.eval(GEOM));
  check('画布宽度不超过卡片', g.cvW <= g.cardW + 1, `canvas ${g.cvW} vs card ${g.cardW}`);

  // ---------- 2) and it must stay stable across redraws
  for (let i = 0; i < 12; i++) {
    await cdp.eval(`window.dispatchEvent(new Event('resize'))`);
    await sleep(60);
  }
  await sleep(400);
  const g2 = JSON.parse(await cdp.eval(GEOM));
  check('多次重绘后尺寸稳定', Math.abs(g2.cvW - g.cvW) <= 1, `${g.cvW} -> ${g2.cvW}`);

  // ---------- 3) clicking 60% of the visible card seeks to ~60% of the clip
  await cdp.eval(`document.querySelectorAll('#tlZoom button')[0].click()`); // 全览
  await sleep(300);
  g = JSON.parse(await cdp.eval(GEOM));
  const x60 = g.cardLeft + g.cardW * 0.6;
  const y = g.cardTop + g.cardH * 0.6;
  await click(cdp, x60, y);
  await sleep(700);
  const st = JSON.parse(await cdp.eval(`JSON.stringify({
    frame: window.__mc.frame, frames: window.__mc.bake.frames,
    fps: window.__mc.bake.fps, dur: window.__mc.clip.duration })`));
  const clickedT = st.frame / st.fps;
  const wantT = st.dur * 0.6;
  const err = Math.abs(clickedT - wantT);
  check('点击位置与时间一致', err < st.dur * 0.06, `点 60% -> ${clickedT.toFixed(2)}s / 期望 ${wantT.toFixed(2)}s`);

  // ---------- 4) zoom actually narrows the visible window ----------
  // Measured by the span between the two ends of the lane, which does not depend
  // on where a previous step left the playhead.
  await cdp.eval(`document.querySelectorAll('#tlZoom button')[0].click()`); // 全览
  await sleep(300);
  await click(cdp, g.cardLeft + g.cardW * 0.02, y);
  await sleep(500);
  const fullA = JSON.parse(await cdp.eval(`JSON.stringify({ frame: window.__mc.frame, fps: window.__mc.bake.fps })`));
  await click(cdp, g.cardLeft + g.cardW * 0.98, y);
  await sleep(500);
  const fullB = JSON.parse(await cdp.eval(`JSON.stringify({ frame: window.__mc.frame, fps: window.__mc.bake.fps })`));
  const fullSpan = Math.abs(fullB.frame - fullA.frame) / fullB.fps;

  await cdp.eval(`document.querySelectorAll('#tlZoom button')[2].click()`); // 4x
  await sleep(400);
  const z = await cdp.eval(`window.__mc.zoom`);
  await click(cdp, g.cardLeft + g.cardW * 0.02, y);
  await sleep(500);
  const zoomA = JSON.parse(await cdp.eval(`JSON.stringify({ frame: window.__mc.frame, fps: window.__mc.bake.fps })`));
  await click(cdp, g.cardLeft + g.cardW * 0.98, y);
  await sleep(500);
  const zoomB = JSON.parse(await cdp.eval(`JSON.stringify({ frame: window.__mc.frame, fps: window.__mc.bake.fps })`));
  const zoomSpan = Math.abs(zoomB.frame - zoomA.frame) / zoomB.fps;

  check(
    '缩放后可见窗口变窄',
    z === 2 && zoomSpan < fullSpan * 0.45 && zoomSpan > 0.05,
    `全览跨度 ${fullSpan.toFixed(2)}s -> 4x ${zoomSpan.toFixed(2)}s`
  );
  await cdp.eval(`document.querySelectorAll('#tlZoom button')[0].click()`);
  await sleep(200);

  // ---------- 5) switching clips clears trims and keyframes
  const nClips = await cdp.eval(`document.getElementById('clipSel').options.length`);
  if (nClips > 1) {
    await cdp.eval(`(() => { window.__mc.trim = { a: 0.4, b: 0.9 }; window.__mc.kfs = [{ t: 0.5, x: 10, y: 10 }]; })()`);
    const res = await cdp.eval(`(async () => {
      const o = document.getElementById('clipSel');
      const other = [...o.options].find(x => x.value !== window.__mc.clip.dir);
      o.value = other.value;
      o.dispatchEvent(new Event('change'));
      await new Promise(r => setTimeout(r, 1600));
      return JSON.stringify({ trim: window.__mc.trim, kfs: window.__mc.kfs.length, dur: window.__mc.clip.duration });
    })()`);
    const r = JSON.parse(res);
    check('切换素材清空裁切/关键帧', r.trim === null && r.kfs === 0, res);
  } else {
    check('切换素材清空裁切/关键帧', true, '仅一个素材，跳过');
  }

  // ---------- 6) timeline still matches the card after a clip switch
  const g3 = JSON.parse(await cdp.eval(GEOM));
  check('切换后画布仍匹配卡片', g3.cvW <= g3.cardW + 1, `${g3.cvW} vs ${g3.cardW}`);

  cdp.close();
  const bad = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - bad}/${results.length} checks passed`);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error('VERIFY ERROR:', e.message); process.exit(2); });
