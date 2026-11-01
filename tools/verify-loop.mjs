// Auto-replay toggle: the boolean control and what it actually changes.
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

const ST = `JSON.stringify({ playing: window.__mc.playing, loop: window.__mc.loop,
  frame: window.__mc.frame, frames: window.__mc.bake ? window.__mc.bake.frames : 0,
  useVideo: window.__mc.useVideo })`;

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
  await sleep(600);

  // ---------- the control exists where it was asked for, and starts off
  const present = await cdp.eval(`(() => {
    const b = document.getElementById('loopToggle');
    if (!b) return 'missing';
    const r = b.getBoundingClientRect();
    return JSON.stringify({ text: b.textContent.trim(), on: b.classList.contains('is-on'),
      x: Math.round(r.x), y: Math.round(r.y), visible: r.width > 0 });
  })()`);
  const p0 = JSON.parse(present === 'missing' ? '{}' : present);
  check('按钮存在且默认关闭', present !== 'missing' && p0.visible && p0.on === false && p0.text === '自动回放', present);

  // ---------- toggling is a boolean and shows checked state
  await cdp.eval(`document.getElementById('loopToggle').click()`);
  await sleep(200);
  const on = await cdp.eval(`(() => { const b = document.getElementById('loopToggle');
    return JSON.stringify({ on: b.classList.contains('is-on'), text: b.textContent.trim(), loop: window.__mc.loop }); })()`);
  const pOn = JSON.parse(on);
  check('勾选后状态与文案同步', pOn.on === true && pOn.loop === true && pOn.text.includes('✓'), on);

  // ---------- with it on, playback wraps to the head instead of stopping
  await cdp.eval(`(() => { const s = window.__mc; s.frame = s.bake.frames - 30; })()`);
  await sleep(150);
  await cdp.eval(`document.getElementById('btnPlay').click()`);
  await sleep(1800);
  const mid = JSON.parse(await cdp.eval(ST));
  const wrapped = mid.playing === true && mid.frame < mid.frames * 0.6;
  check('播到尾帧后自动回到首帧继续播', wrapped, `playing=${mid.playing} frame=${mid.frame}/${mid.frames}`);

  // ---------- and it really keeps going (not a one-shot restart that stalls)
  const f1 = JSON.parse(await cdp.eval(ST)).frame;
  await sleep(700);
  const f2 = JSON.parse(await cdp.eval(ST)).frame;
  check('回放后仍在推进', f2 !== f1, `${f1} -> ${f2}`);

  await cdp.eval(`document.getElementById('btnPlay').click()`);
  await sleep(300);

  // ---------- with it off, playback still stops at the end
  await cdp.eval(`document.getElementById('loopToggle').click()`);
  await sleep(150);
  await cdp.eval(`(() => { const s = window.__mc; s.frame = s.bake.frames - 12; })()`);
  await sleep(120);
  await cdp.eval(`document.getElementById('btnPlay').click()`);
  await sleep(2200);
  const end = JSON.parse(await cdp.eval(ST));
  check('关闭后在尾帧停下', end.playing === false && end.frame >= end.frames - 2,
    `playing=${end.playing} frame=${end.frame}/${end.frames}`);

  const errs = cdp.events.filter((e) => e.method === 'Runtime.consoleAPICalled' && e.params.type === 'error');
  check('无 console 错误', errs.length === 0, `${errs.length}`);

  const shot = await cdp.send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync('shots/65_loop_toggle.png', Buffer.from(shot.data, 'base64'));

  cdp.close();
  const bad = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - bad}/${results.length} checks passed`);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error('VERIFY ERROR:', e.message); process.exit(2); });
