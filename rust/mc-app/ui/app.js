/* ============================================================
   MouseCam — editor front-end
   ============================================================ */
/* Transport shim: the same UI runs inside Tauri (IPC) or in a plain browser
   against the local demo server. Only this block differs. */
const T = window.__TAURI__;
const IS_TAURI = !!(T && T.core);

async function httpInvoke(cmd, args) {
  const r = await fetch('/api/' + cmd, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args || {}),
  });
  const j = await r.json();
  if (!j.ok) throw j.error;
  return j.data;
}

// Frontend failures are invisible unless someone has DevTools open, so they go
// into the same log file as the Rust side.
function logUi(level, msg) {
  try {
    if (IS_TAURI) {
      T.core.invoke('log_event', { level, msg: String(msg) }).catch(() => {});
    }
  } catch (_) { /* logging must never throw */ }
}

window.addEventListener('error', (e) => {
  logUi('error', `JS 异常: ${e.message} @ ${e.filename}:${e.lineno}:${e.colno}`);
});
window.addEventListener('unhandledrejection', (e) => {
  const r = e && e.reason;
  logUi('error', `未处理的 Promise 拒绝: ${(r && (r.stack || r.message)) || r}`);
});
const _consoleError = console.error.bind(console);
console.error = (...a) => {
  _consoleError(...a);
  logUi('error', a.map((x) => (x && x.stack) || String(x)).join(' '));
};

// Commands that are expected to fail now and then (the preview poller runs
// before the engine is ready) would otherwise flood the log at 8 lines/second.
// media_path fails for every clip that has no proxy yet, which is normal.
// preview_frame used to be silenced because it fails at 8 Hz while the engine
// warms up; the Rust logger collapses identical consecutive lines, so it is safe
// to surface now - and a preview that stops producing frames must not be silent.
const QUIET_CALLS = new Set(['record_status', 'hud_get', 'hud_get_config', 'media_path', 'still', 'heartbeat']);

function traced(fn) {
  return async (cmd, args) => {
    try {
      return await fn(cmd, args);
    } catch (e) {
      if (!QUIET_CALLS.has(cmd)) logUi('error', `调用 ${cmd} 失败: ${e}`);
      throw e;
    }
  };
}

const invoke = traced(IS_TAURI ? T.core.invoke.bind(T.core) : httpInvoke);
const getWin = () => (IS_TAURI ? T.window.getCurrentWindow() : null);
const mediaUrl = IS_TAURI
  ? (p) => T.core.convertFileSrc(p)
  : (p) => '/media?p=' + encodeURIComponent(p);

const $ = (id) => document.getElementById(id);

/* ---------------- state ---------------- */
const state = {
  clips: [],
  clip: null,
  track: [],
  bake: null,          // { frames, fps, duration, mon, path, ticks }
  frame: 0,
  playing: false,
  playing_rafs: 0,
  zoom: 0,
  edit: {
    zoom: 1.0,
    expand: 1.2,
    threshold: 3400,
    smooth: 66,
    resp: 35,
    follow: 1.0,
    look: 60,
    aspect: 0,
    width: 1080,
  },
  stillInFlight: false,
  stillPending: false,
  dirty: false,
  trim: null,           // {a, b} seconds on the source timeline, null = whole clip
  kfs: [],              // [{t, x, y}] manual follow points
  kfMode: false,
  trimMode: false,
  loop: false,
  monitor: 0,
  lastToggle: 0,
  hotkeys: null,
  hw: false,
  nvenc: null,
  appSettings: null,
  recording: false,
  recDir: '',
  recTimer: 0,
  proxyPath: '',
  proxyBusy: false,
  proxyReady: false,
  proxyStale: false,
  useVideo: false,
};

const DEFAULTS = { ...state.edit };

// Camera parameters are a preference, not a per-project setting: retyping nine
// values every launch is the thing that makes a tool tiring to use.
const PARAMS_KEY = 'mc.params';
const SAVED_PARAMS = (() => {
  try {
    const v = JSON.parse(localStorage.getItem(PARAMS_KEY) || '{}');
    return v && typeof v === 'object' ? v : {};
  } catch { return {}; }
})();

function loadSavedParams() {
  const e = SAVED_PARAMS.edit;
  if (e && typeof e === 'object') {
    for (const k of Object.keys(DEFAULTS)) {
      if (typeof e[k] === 'number' && Number.isFinite(e[k])) state.edit[k] = e[k];
    }
  }
}

function saveParams() {
  try {
    localStorage.setItem(PARAMS_KEY, JSON.stringify({ edit: state.edit, hud: hudCfg }));
  } catch {}
}

const ASPECTS = [
  ['16:9', 16 / 9],
  ['9:16', 9 / 16],
  ['1:1', 1],
  ['4:3', 4 / 3],
  ['21:9', 21 / 9],
  ['3:2', 3 / 2],
];

/* ---------------- utils ---------------- */
function tc(t) {
  if (!isFinite(t)) t = 0;
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  return `${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`;
}

function toast(msg, ms = 1800) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove('show'), ms);
}

function editText() {
  const e = state.edit;
  const lines = [
    `zoom ${e.zoom}`,
    `expand ${e.expand}`,
    `threshold ${e.threshold}`,
    `smooth ${e.smooth}`,
    `resp ${e.resp}`,
    `follow ${e.follow}`,
    `look ${e.look}`,
    `aspect ${e.aspect}`,
    `width ${e.width}`,
  ];
  if (state.trim) lines.push(`trim ${state.trim.a.toFixed(3)} ${state.trim.b.toFixed(3)}`);
  for (const k of state.kfs) lines.push(`kf ${k.t.toFixed(3)} ${Math.round(k.x)} ${Math.round(k.y)}`);
  return lines.join('\n');
}

function fmtRecTime(sec) {
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${String(m).padStart(2, '0')}:${s.toFixed(1).padStart(4, '0')}`;
}

function setRecording(on) {
  state.recording = on;
  const orb = $('recOrb');
  orb.classList.toggle('is-recording', on);
  $('recTime').classList.toggle('is-recording-time', on);
  $('recHint').textContent = on
    ? '正在录制 — 点击方形按钮停止'
    : '主显示器 · 30 fps · 同时生成原片 / 跟拍 / 轨迹';
  $('recState').textContent = on ? '录制中' : '待机';
  const sel = $('recMonitor');
  if (sel) sel.disabled = on;
  paintRecHint();
  if (on) {
    state.recTimer = setInterval(async () => {
      try {
        const st = await invoke('record_status');
        if (st && st.recording) $('recTime').textContent = fmtRecTime(st.elapsed);
      } catch {}
    }, 200);
  } else {
    clearInterval(state.recTimer);
  }
  const ht = $('hudToggle');
  if (ht) {
    ht.classList.toggle('is-disabled', on);
    ht.title = on ? '录制期间取景框自动隐藏' : '在屏幕上显示跟拍取景框（不会被录进去）';
  }
}

// Desktop duplication ignores WDA_EXCLUDEFROMCAPTURE, so a visible frame lands
// inside master.mp4 and camera.mp4. Hiding it for the duration of a recording is
// the only reliable way to keep the border out of the picture.
let hudSuspendedForRecording = false;
let hudSuspendHintShown = false;

async function suspendHudForRecording() {
  const btn = $('hudToggle');
  if (!btn || !btn.classList.contains('is-on')) return;
  hudSuspendedForRecording = true;
  btn.classList.remove('is-on');
  try { await invoke('hud_set', { enabled: false }); } catch {}
  if (!hudSuspendHintShown) {
    hudSuspendHintShown = true;
    toast('录制期间已隐藏取景框（否则会录进画面）', 2600);
  }
  // let the overlay process hide before the first frame is grabbed
  await new Promise((r) => setTimeout(r, 140));
}

async function restoreHudAfterRecording() {
  if (!hudSuspendedForRecording) return;
  hudSuspendedForRecording = false;
  const btn = $('hudToggle');
  if (btn) btn.classList.add('is-on');
  try { await invoke('hud_set', { enabled: true }); } catch {}
}

async function toggleRecord() {
  if (state.proxyBusy) return;
  state.lastToggle = Date.now();
  if (!state.recording) {
    try {
      await restoreHudAfterRecording();
      $('recWarn').textContent = '';
      await suspendHudForRecording();
      const dir = await invoke('record_start', {
        edit: editText(),
        monitor: state.monitor,
        hw: state.hw,
      });
      state.recDir = dir;
      $('recTime').textContent = '00:00.0';
      setRecording(true);
    } catch (e) {
      $('recWarn').textContent = '启动失败: ' + e;
    }
  } else {
    try {
      $('recHint').textContent = '正在写入文件…';
      const msg = await invoke('record_stop');
      setRecording(false);
      await restoreHudAfterRecording();
      state.proxyPath = '';
      await loadClips();
      if (state.recDir) {
        const c = state.clips.find((x) => x.dir === state.recDir);
        if (c) await selectClip(c.dir);
      }
      toast('录制完成 ' + msg, 3200);
      document.querySelector('.tab[data-tab="edit"]').click();
    } catch (e) {
      setRecording(false);
      $('recWarn').textContent = '停止失败: ' + e;
    }
  }
}

$('recOrb').onclick = toggleRecord;

// The global hotkey toggles recording inside the Rust side, so the page has to
// notice and catch up - otherwise it keeps showing 待机 while recording runs.
async function syncRecordingState() {
  if (!IS_TAURI) return;
  if (Date.now() - (state.lastToggle || 0) < 1500) return; // the button is driving
  let st;
  try {
    st = await invoke('record_status');
  } catch {
    return;
  }
  const on = !!(st && st.recording);
  if (on === state.recording) return;

  if (on) {
    state.recDir = st.dir || '';
    $('recTime').textContent = '00:00.0';
    setRecording(true);
    toast('已通过快捷键开始录制', 2000);
  } else {
    setRecording(false);
    await loadClips();
    if (state.recDir) {
      const c = state.clips.find((x) => x.dir === state.recDir);
      if (c) await selectClip(c.dir);
    }
    toast('录制已结束', 2400);
  }
}

setInterval(syncRecordingState, 800);

$('recHw').onchange = () => {
  state.hw = $('recHw').checked;
};

$('recMonitor').onchange = async (ev) => {
  state.monitor = Number(ev.target.value) || 0;
  paintRecHint();
  await restartPreview();
};

const hudCfg = {
  thickness: 2,
  label: true,
  brackets: true,
  ...(SAVED_PARAMS.hud && typeof SAVED_PARAMS.hud === 'object' ? SAVED_PARAMS.hud : {}),
};

function pushHudConfig() {
  saveParams();
  if (!IS_TAURI) return;
  invoke('hud_set_config', {
    thickness: hudCfg.thickness,
    label: hudCfg.label,
    brackets: hudCfg.brackets,
  }).catch(() => {});
}

$('hudWidth').oninput = () => {
  hudCfg.thickness = Number($('hudWidth').value);
  $('hudWidthVal').textContent = hudCfg.thickness;
  pushHudConfig();
};
$('hudLabel').onchange = () => {
  hudCfg.label = $('hudLabel').checked;
  pushHudConfig();
};

  // reflect whatever was restored, otherwise the row lies about the frame width
  $('hudWidth').value = hudCfg.thickness;
  $('hudWidthVal').textContent = hudCfg.thickness;
  $('hudLabel').checked = !!hudCfg.label;
  if ($('hudBrackets')) $('hudBrackets').checked = !!hudCfg.brackets;
$('hudBrackets').onchange = () => {
  hudCfg.brackets = $('hudBrackets').checked;
  pushHudConfig();
};

$('hudToggle').onclick = async () => {
  // turning it back on mid-recording would write the border into the file
  if (state.recording) {
    toast('录制期间取景框会自动隐藏，停止后可重新打开', 2200);
    return;
  }
  const on = !$('hudToggle').classList.contains('is-on');
  $('hudToggle').classList.toggle('is-on', on);
  try {
    await invoke('hud_set', { enabled: on });
    state.hudOn = on;
    toast(on ? '取景框已开启' : '取景框已关闭', 1400);
  } catch (e) {
    toast('切换失败: ' + e);
  }
};

$('recReset').onclick = async () => {
  state.edit = { ...DEFAULTS };
  buildParams('paramsGrid');
  buildParams('recParamsGrid');
  if (state.recPreviewOn) {
    invoke('preview_set_params', { edit: editText() }).catch(() => {});
  }
  await rebake();
  drawLeft();
  scheduleStill();
};

function fitInside(cw, ch, iw, ih) {
  let w = cw, h = w * (ih / iw);
  if (h > ch) { h = ch; w = h * (iw / ih); }
  return { x: (cw - w) / 2, y: (ch - h) / 2, w, h };
}

function sizeCanvas(cv) {
  const dpr = window.devicePixelRatio || 1;
  const parent = cv.parentElement;
  // clientWidth/Height = padding box; the canvas is absolutely positioned to
  // fill exactly that, and its CSS size is never touched (writing style.width
  // here used to feed a growth loop back into the parent).
  const pw = Math.floor(parent.clientWidth);
  const ph = Math.floor(parent.clientHeight);
  if (pw < 2 || ph < 2) {
    // The tab is hidden (display:none). Keep the existing backing store rather
    // than resizing it to 1x1, which used to leave a stretched single pixel.
    const ctx = cv.getContext('2d');
    if (!ctx) return { ctx, w: 1, h: 1 };
    ctx.setTransform(window.devicePixelRatio || 1, 0, 0, window.devicePixelRatio || 1, 0, 0);
    return { ctx, w: cv.width / (window.devicePixelRatio || 1), h: cv.height / (window.devicePixelRatio || 1) };
  }
  const w = Math.max(1, pw);
  const h = Math.max(1, ph);
  const bw = Math.round(w * dpr);
  const bh = Math.round(h * dpr);
  if (cv.width !== bw || cv.height !== bh) {
    cv.width = bw;
    cv.height = bh;
  }
  const ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

/* ---------------- window controls ---------------- */
if (IS_TAURI) {
  $('wbMin').onclick = () => getWin().minimize();
  $('wbMax').onclick = () => getWin().toggleMaximize();

  $('wbClose').onclick = () => getWin().close();
} else {
  // browser demo: no native chrome to drive
  document.querySelector('.winbtns').style.visibility = 'hidden';
  document.body.classList.add('is-web');
}

/* ---------------- app settings ---------------- */
async function loadAppSettings() {
  try {
    const [effective, configured, hw, hud, verbose] = await invoke('app_settings');
    state.appSettings = { effective, configured, hw, hud, verbose };
  } catch (e) {
    // Never swallow this silently: a failed read here decides the output folder
    // and the default encode mode for the whole session.
    logUi('error', `读取设置失败: ${e}`);
    state.appSettings = null;
  }
  return state.appSettings;
}

function paintSettingsDialog() {
  const a = state.appSettings || {};
  $('setCaptures').value = a.configured || '';
  $('setCaptures').placeholder = a.effective || '默认位置';
  // When the configured folder cannot be written the engine falls back to
  // one that can; saying so here answers "why did my recordings go elsewhere".
  const configured = (a.configured || '').trim();
  const effective = (a.effective || '').trim();
  if (effective && configured && configured !== effective) {
    $('setCapturesHint').textContent = `该文件夹不可写（常见于安全软件拦截），实际使用：${effective}`;
    $('setCapturesHint').classList.add('is-warn');
  } else {
    $('setCapturesHint').textContent = `当前生效：${effective || '（未知）'}`;
    $('setCapturesHint').classList.remove('is-warn');
  }
  $('setHw').checked = !!a.hw;
  $('setHud').checked = !!a.hud;
  if ($('setVerbose')) $('setVerbose').checked = !!a.verbose;
  $('setAbout').textContent = `MouseCam ${state.version || ''} · 编辑页的素材列表来自上面的文件夹`;
}

$('wbSettings').onclick = async () => {
  await loadAppSettings();
  paintSettingsDialog();
  $('settingsModal').classList.remove('is-hidden');
};

$('setCancel').onclick = () => $('settingsModal').classList.add('is-hidden');
$('settingsModal').addEventListener('mousedown', (e) => {
  if (e.target === $('settingsModal')) $('settingsModal').classList.add('is-hidden');
});

if ($('setOpenLog')) {
  $('setOpenLog').onclick = async () => {
    try {
      await invoke('open_log');
    } catch (e) {
      toast('无法打开日志: ' + e, 3000);
    }
  };
}

$('setOpen').onclick = async () => {
  const p = $('setCaptures').value.trim() || (state.appSettings && state.appSettings.effective) || '';
  if (!p) return;
  try {
    await invoke('open_folder', { dir: p });
  } catch (e) {
    toast('无法打开文件夹: ' + e, 3000);
  }
};

$('setDefault').onclick = () => {
  $('setCaptures').value = '';
  $('setCaptures').placeholder = '默认位置';
};

$('setSave').onclick = async () => {
  const dir = $('setCaptures').value.trim();
  const hw = $('setHw').checked;
  const hud = $('setHud').checked;
  const verbose = $('setVerbose') ? $('setVerbose').checked : false;
  try {
    await invoke('set_app_settings', { capturesDir: dir, hw, hud, verbose });
    await loadAppSettings();
    // apply immediately where it is cheap to do so
    state.hw = !!hw && !!state.nvenc;
    const box = $('recHw');
    if (box) box.checked = state.hw;
    $('hudToggle').classList.toggle('is-on', !!hud);
    await invoke('hud_set', { enabled: !!hud });
    $('settingsModal').classList.add('is-hidden');
    await loadClips();
    toast('设置已保存', 2200);
  } catch (e) {
    toast('保存失败: ' + e, 4000);
  }
};

/* ---------------- tabs ---------------- */
const tabsEl = document.querySelector('.tabs');
const glider = document.querySelector('.tab-glider');

function moveGlider(btn) {
  glider.style.width = btn.offsetWidth + 'px';
  glider.style.transform = `translateX(${btn.offsetLeft - 3}px)`;
}

document.querySelectorAll('.tab').forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll('.tab').forEach((b) => b.classList.remove('is-active'));
    btn.classList.add('is-active');
    moveGlider(btn);
    const rec = btn.dataset.tab === 'record';
    $('stageEdit').classList.toggle('is-hidden', rec);
    $('stageRecord').classList.toggle('is-hidden', !rec);
    if (rec) enterRecordTab();
    else leaveRecordTab();
  };
});

/* ---------------- params ---------------- */
const PARAMS = [
  { key: 'zoom', label: '视口缩放', min: 0.5, max: 3, step: 0.01, fmt: (v) => v.toFixed(2) + '×' },
  { key: 'width', label: '宽度', type: 'select', options: [[854, '854'], [1080, '1080'], [1280, '1280'], [1440, '1440'], [1920, '1920']] },
  { key: 'aspect', label: '画面比例', type: 'select', options: ASPECTS.map((a, i) => [i, a[0]]) },
  { key: 'expand', label: '快移放大', min: 1, max: 3, step: 0.05, fmt: (v) => v.toFixed(2) + '×' },
  { key: 'threshold', label: '触发阈值', min: 200, max: 6000, step: 50, fmt: (v) => Math.round(v) + ' px/s' },
  { key: 'smooth', label: '平滑系数', min: 0, max: 100, step: 1, fmt: (v) => Math.round(v) },
  { key: 'resp', label: '速度响应', min: 0, max: 100, step: 1, fmt: (v) => Math.round(v) },
  { key: 'follow', label: '跟随速度', min: 0.4, max: 6, step: 0.1, fmt: (v) => v.toFixed(1) + ' Hz' },
  { key: 'look', label: '前瞻量', min: 0, max: 300, step: 5, fmt: (v) => Math.round(v) + ' ms' },
];

function buildParams(target) {
  const grid = $(target || 'paramsGrid');
  grid.innerHTML = '';
  for (const p of PARAMS) {
    const row = document.createElement('div');
    row.className = 'row';
    const lab = document.createElement('span');
    lab.className = 'row-label';
    lab.textContent = p.label;
    row.appendChild(lab);

    if (p.type === 'select') {
      const sel = document.createElement('select');
      for (const [v, t] of p.options) {
        const o = document.createElement('option');
        o.value = v;
        o.textContent = t;
        sel.appendChild(o);
      }
      sel.value = state.edit[p.key];
      sel.onchange = () => {
        state.edit[p.key] = Number(sel.value);
        onParamChanged();
      };
      const wrap = document.createElement('div');
      wrap.style.gridColumn = 'span 2';
      wrap.appendChild(sel);
      row.appendChild(wrap);
    } else {
      const inp = document.createElement('input');
      inp.type = 'range';
      inp.min = p.min;
      inp.max = p.max;
      inp.step = p.step;
      inp.value = state.edit[p.key];
      const val = document.createElement('span');
      val.className = 'row-val';
      const paint = () => {
        const pct = ((inp.value - p.min) / (p.max - p.min)) * 100;
        inp.style.setProperty('--pct', pct + '%');
        val.textContent = p.fmt(Number(inp.value));
      };
      paint();
      inp.oninput = () => {
        state.edit[p.key] = Number(inp.value);
        paint();
        onParamChanged();
      };

      // Double-click the number to type an exact value. The slider cannot be
      // precise enough by hand, and the parameter ranges are wide (0.5-3.0 zoom,
      // 200-6000 px/s), so typing is the only practical way to hit a value.
      val.title = '双击输入数值';
      val.ondblclick = () => {
        if (val.dataset.editing) return;
        val.dataset.editing = '1';
        const before = Number(inp.value);
        const ed = document.createElement('input');
        ed.type = 'text';
        ed.className = 'row-val-edit';
        ed.value = String(Number(before.toFixed(6)));
        ed.inputMode = 'decimal';
        val.textContent = '';
        val.appendChild(ed);
        ed.focus();
        ed.select();

        let done = false;
        const finish = (commit) => {
          if (done) return;
          done = true;
          delete val.dataset.editing;
          // Detach first: replacing the node can fire blur, which would
          // otherwise re-enter here and commit twice.
          ed.onblur = null;
          val.textContent = '';
          if (commit) {
            const raw = ed.value.replace(',', '.').replace(/[^0-9.\-]/g, '');
            const n = parseFloat(raw);
            if (Number.isFinite(n)) {
              inp.value = String(Math.min(p.max, Math.max(p.min, n)));
              state.edit[p.key] = Number(inp.value);
              onParamChanged();
            }
          }
          paint();
        };
        ed.onkeydown = (e) => {
          // The window-wide handler watches for F9/F10; typing "3" must not
          // start a recording, and Escape must not clear the selection.
          e.stopPropagation();
          if (e.key === 'Enter') {
            e.preventDefault();
            finish(true);
          } else if (e.key === 'Escape') {
            e.preventDefault();
            finish(false);
          }
        };
        ed.onblur = () => finish(true);
      };
      row.appendChild(inp);
      row.appendChild(val);
    }
    grid.appendChild(row);
  }
}

function scheduleRebake() {
  clearTimeout(rebakeTimer);
  rebakeTimer = setTimeout(async () => {
    await rebake();
    state.proxyStale = true;
    $('btnProxy').classList.add('is-on');
    drawLeft();
    scheduleStill();
  }, 60);
}

let rebakeTimer = 0;
function onParamChanged() {
  saveParams();
  clearTimeout(rebakeTimer);
  rebakeTimer = setTimeout(async () => {
    await rebake();
    state.proxyStale = true;
    $('btnProxy').classList.add('is-on');
    drawLeft();
    scheduleStill();
  }, 45);
  if (state.recPreviewOn) {
    invoke('preview_set_params', { edit: editText() }).catch(() => {});
  }
}

$('clipSel').onchange = (e) => selectClip(e.target.value);

$('kfToggle').onclick = () => {
  state.kfMode = !state.kfMode;
  $('kfToggle').classList.toggle('is-on', state.kfMode);
  $('viewCanvas').style.cursor = state.kfMode ? 'crosshair' : '';
  if (!state.kfMode) return;
  toast(state.kfs.length < 2 ? '在画面上拖动：至少 2 个跟随点才会生效' : '拖动绿点可调整跟随位置', 2600);
};

function paintLoopToggle() {
  const b = $('loopToggle');
  b.classList.toggle('is-on', state.loop);
  b.textContent = state.loop ? '✓ 自动回放' : '自动回放';
}

$('loopToggle').onclick = () => {
  state.loop = !state.loop;
  paintLoopToggle();
  pushHudConfig();
  toast(state.loop ? '播放到尾帧会自动回到首帧' : '自动回放已关闭', 1500);
};

$('trimToggle').onclick = () => {
  state.trimMode = !state.trimMode;
  $('trimToggle').classList.toggle('is-on', state.trimMode);
  document.getElementById('tlCanvas').style.cursor = state.trimMode ? 'crosshair' : '';
  if (state.trimMode) toast('在时间线上拖动框选要保留的区间', 2600);
};

$('btnTrimClear').onclick = () => {
  state.trim = null;
  drawTimeline();
  drawLeft();
};

$('btnReset').onclick = async () => {
  state.edit = { ...DEFAULTS };
  buildParams();
  await rebake();
  drawLeft();
  scheduleStill();
};

$('btnExport').onclick = () => {
  if (!state.clip) return;
  $('exportModal').classList.remove('is-hidden');
  $('exHint').textContent = `输出到 ${state.clip.dir}\\export.*`;
};

$('exQuality').oninput = () => {
  $('exQualityVal').textContent = $('exQuality').value;
};

$('exCancel').onclick = () => $('exportModal').classList.add('is-hidden');

$('exportModal').addEventListener('mousedown', (e) => {
  if (e.target === $('exportModal')) $('exportModal').classList.add('is-hidden');
});

$('exGo').onclick = async () => {
  if (!state.clip) return;
  const btn = $('exGo');
  const openedAt = Date.now();
  btn.disabled = true;
  btn.textContent = '导出中…';
  $('btnExport').disabled = true;
  $('btnExport').textContent = '导出中…';
  try {
    const r = await invoke('export', {
      dir: state.clip.dir,
      edit: editText(),
      out: '',
      format: $('exFormat').value,
      quality: Number($('exQuality').value),
      width: Number($('exWidth').value),
      fps: Number($('exFps').value),
    });
    $('exportModal').classList.add('is-hidden');
    toast('已导出 ' + r, 4200);
    state.exportFormat = $('exFormat').value;
  } catch (e) {
    toast('导出失败: ' + e, 5000);
  } finally {
    // keep the button readable for at least a moment on fast exports
    const wait = Math.max(0, 350 - (Date.now() - openedAt));
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = '开始导出';
      $('btnExport').disabled = false;
      $('btnExport').textContent = '导出';
    }, wait);
  }
};

/* ---------------- data ---------------- */
function fillClipSelect() {
  const sel = $('clipSel');
  sel.innerHTML = '';
  for (const c of state.clips) {
    const o = document.createElement('option');
    o.value = c.dir;
    o.textContent = `${c.name}  ·  ${tc(c.duration)}`;
    sel.appendChild(o);
  }
  if (state.clip) sel.value = state.clip.dir;
}

async function selectClip(dir) {
  const c = state.clips.find((x) => x.dir === dir);
  if (!c) return;
  state.clip = c;
  state.frame = 0;
  state.viewImg = null;
  state.cropImg = null;
  $('monInfo').textContent = `${c.mon_w}×${c.mon_h} · ${c.fps}fps`;
  $('tcTotal').textContent = tc(c.duration);
  state.track = await invoke('track_points', { dir: c.dir });
  state.proxyReady = false;
  state.proxyStale = false;
  // trims and keyframes are clip-specific: times from the old clip are
  // meaningless (or out of range) on the new one
  state.trim = null;
  state.kfs = [];
  $('cropVideo').classList.remove('is-on');
  await rebake();
  await setupMedia();
  drawTimeline();
  drawLeft();
  drawRight();
  scheduleStill();
}

async function loadClips() {
  state.clips = await invoke('list_clips');
  if (!state.clips.length) {
    $('viewEmpty').textContent = '没有找到录制素材';
    $('clipSel').style.display = 'none';
    return false;
  }
  fillClipSelect();
  state.clip = state.clips[0];
  $('monInfo').textContent = `${state.clip.mon_w}×${state.clip.mon_h} · ${state.clip.fps}fps`;
  $('tcTotal').textContent = tc(state.clip.duration);
  $('viewEmpty').style.display = 'none';
  $('cropEmpty').style.display = 'none';
  state.track = await invoke('track_points', { dir: state.clip.dir });
  await rebake();
  return true;
}

async function rebake() {
  if (!state.clip) return;
  try {
    state.bake = await invoke('api_bake', { dir: state.clip.dir, edit: editText() });
  } catch (e) {
    toast('参数烘焙失败: ' + e);
  }
}

async function fetchStill(kind, maxW) {
  const p = invoke('still', {
    dir: state.clip.dir,
    edit: editText(),
    frame: state.frame,
    maxW,
    kind,
  });
  return p;
}

function seekVideos(t) {
  for (const el of [$('viewVideo'), $('cropVideo')]) {
    if (!el.classList.contains('is-on')) continue;
    if (Math.abs(el.currentTime - t) > 0.02) {
      try { el.currentTime = t; } catch {}
    }
  }
}

function scheduleStill() {
  const fps = state.bake ? state.bake.fps : 30;
  const cropFromVideo = state.proxyReady && !state.proxyStale;

  // The master video has to follow the playhead even without a proxy, otherwise
  // clicking the timeline only moves the trace and the right pane. Never seek
  // while playing: the video IS the clock then, and seeking from state.frame
  // would drag it back every time this runs.
  if (state.useVideo && !state.playing) seekVideos(state.frame / fps);
  if (state.useVideo && cropFromVideo) {
    drawLeft();
    drawRight();
    return;
  }
  state.stillPending = true;
  if (state.stillInFlight) return;
  state.stillInFlight = true;
  (async () => {
    while (state.stillPending && state.clip) {
      state.stillPending = false;
      const f = state.frame;
      try {
        const [view, crop] = await Promise.all([fetchStill('view', 900), fetchStill('crop', 620)]);
        if (Math.abs(f - state.frame) < 2) {
          state.viewImg = await loadImg(view);
          state.cropImg = await loadImg(crop);
        }
        drawLeft();
        drawRight();
      } catch (e) {
        /* seek/decode race — ignore */
      }
    }
    state.stillInFlight = false;
  })();
}

function loadImg(src) {
  return new Promise((res, rej) => {
    const i = new Image();
    i.onload = () => res(i);
    i.onerror = rej;
    i.src = src;
  });
}

/* ---------------- left viewport ---------------- */
function viewMapping() {
  const cv = $('viewCanvas');
  const r = cv.parentElement.getBoundingClientRect();
  const w = Math.max(1, Math.floor(r.width));
  const h = Math.max(1, Math.floor(r.height));
  const mon = state.bake ? state.bake.mon : [0, 0, 1920, 1080];
  const box = fitInside(w, h, mon[2], mon[3]);
  return { w, h, mon, box, sx: box.w / mon[2], sy: box.h / mon[3] };
}

function drawLeft() {
  const cv = $('viewCanvas');
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);

  const m = viewMapping();
  const { mon, box } = m;

  if (!state.useVideo) {
    ctx.fillStyle = '#05070a';
    ctx.fillRect(box.x, box.y, box.w, box.h);
  }

  if (state.viewImg && !state.useVideo) ctx.drawImage(state.viewImg, box.x, box.y, box.w, box.h);

  const dur = state.clip ? state.clip.duration : 1;

  // ---- cursor trace
  if (state.track.length) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(box.x, box.y, box.w, box.h);
    ctx.clip();

    const head = state.frame / Math.max(1, state.bake ? state.bake.frames - 1 : 1);

    ctx.strokeStyle = 'rgba(120,150,200,.24)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < state.track.length; i++) {
      const t = state.track[i];
      const x = box.x + (t[1] - mon[0]) * m.sx;
      const y = box.y + (t[2] - mon[1]) * m.sy;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.stroke();

    ctx.strokeStyle = 'rgba(79,140,255,.85)';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    let started = false;
    for (const t of state.track) {
      if (t[0] > head * dur) break;
      const x = box.x + (t[1] - mon[0]) * m.sx;
      const y = box.y + (t[2] - mon[1]) * m.sy;
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  // ---- current viewport
  if (state.bake && state.bake.path[state.frame]) {
    const p = state.bake.path[state.frame];
    const vw = p[2], vh = p[3];
    const rx = box.x + (p[0] - vw / 2 - mon[0]) * m.sx;
    const ry = box.y + (p[1] - vh / 2 - mon[1]) * m.sy;
    const rw = vw * m.sx, rh = vh * m.sy;

    ctx.save();
    ctx.fillStyle = 'rgba(5,8,12,.40)';
    ctx.beginPath();
    ctx.rect(box.x, box.y, box.w, box.h);
    ctx.rect(rx, ry, rw, rh);
    ctx.fill('evenodd');
    ctx.restore();

    ctx.strokeStyle = 'rgba(79,140,255,.95)';
    ctx.lineWidth = 1.4;
    ctx.strokeRect(rx + .5, ry + .5, rw - 1, rh - 1);

    ctx.strokeStyle = '#4f8cff';
    ctx.lineWidth = 2;
    const k = Math.min(12, rw * .18, rh * .18);
    ctx.beginPath();
    ctx.moveTo(rx, ry + k); ctx.lineTo(rx, ry); ctx.lineTo(rx + k, ry);
    ctx.moveTo(rx + rw - k, ry); ctx.lineTo(rx + rw, ry); ctx.lineTo(rx + rw, ry + k);
    ctx.moveTo(rx + rw, ry + rh - k); ctx.lineTo(rx + rw, ry + rh); ctx.lineTo(rx + rw - k, ry + rh);
    ctx.moveTo(rx + k, ry + rh); ctx.lineTo(rx, ry + rh); ctx.lineTo(rx, ry + rh - k);
    ctx.stroke();

    $('frameInfo').textContent = `帧 ${state.frame} / ${state.bake.frames - 1}`;
    $('cropInfo').textContent = `${Math.round(p[2])}×${Math.round(p[3])}`;
    const base = state.edit.width / state.edit.zoom;
    const grow = p[2] / base;
    $('expandInfo').textContent = grow > 1.02 ? `×${grow.toFixed(2)} 快移扩展` : '标准';
  }

  // ---- manual keyframes
  if (state.kfs.length) {
    const ct = state.frame / (state.bake ? state.bake.fps : 30);
    for (const kf of state.kfs) {
      const x = box.x + (kf.x - mon[0]) * m.sx;
      const y = box.y + (kf.y - mon[1]) * m.sy;
      const active = Math.abs(kf.t - ct) < 0.5 / (state.bake ? state.bake.fps : 30);
      ctx.beginPath();
      ctx.arc(x, y, active ? 6 : 4.5, 0, Math.PI * 2);
      ctx.fillStyle = active ? '#2ee6a8' : 'rgba(46,230,168,.35)';
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = active ? '#0a0c10' : 'rgba(10,12,16,.7)';
      ctx.stroke();
      if (active) {
        ctx.beginPath();
        ctx.arc(x, y, 10, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(46,230,168,.55)';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
    }
  }
}

// ---- keyframe editing on the left viewport
let kfDrag = null;

function viewPointToScreen(ev) {
  const cv = $('viewCanvas');
  const r = cv.getBoundingClientRect();
  const m = viewMapping();
  const px = ev.clientX - r.left;
  const py = ev.clientY - r.top;
  if (px < m.box.x || px > m.box.x + m.box.w || py < m.box.y || py > m.box.y + m.box.h) return null;
  return {
    x: m.mon[0] + (px - m.box.x) / m.sx,
    y: m.mon[1] + (py - m.box.y) / m.sy,
    px, py, m,
  };
}

$('viewCanvas').addEventListener('mousedown', (ev) => {
  if (!state.kfMode || !state.bake) return;
  const p = viewPointToScreen(ev);
  if (!p) return;
  const fps = state.bake.fps;
  const t = state.frame / fps;

  // grab the nearest existing keyframe within 14 px
  let best = null, bestD = 14;
  for (let i = 0; i < state.kfs.length; i++) {
    const kf = state.kfs[i];
    const kx = p.m.box.x + (kf.x - p.m.mon[0]) * p.m.sx;
    const ky = p.m.box.y + (kf.y - p.m.mon[1]) * p.m.sy;
    const d = Math.hypot(kx - p.px, ky - p.py);
    if (d < bestD) { bestD = d; best = i; }
  }
  if (best === null) {
    state.kfs.push({ t, x: p.x, y: p.y });
    best = state.kfs.length - 1;
  }
  state.kfs.sort((a, b) => a.t - b.t);
  best = state.kfs.findIndex((k) => Math.abs(k.t - t) < 1e-6);
  kfDrag = best >= 0 ? best : null;
  drawLeft();
  scheduleRebake();
  ev.preventDefault();
});

window.addEventListener('mousemove', (ev) => {
  if (kfDrag === null) return;
  const p = viewPointToScreen(ev);
  if (!p) return;
  state.kfs[kfDrag].x = p.x;
  state.kfs[kfDrag].y = p.y;
  drawLeft();
});

window.addEventListener('mouseup', () => {
  if (kfDrag === null) return;
  kfDrag = null;
  scheduleRebake();
});

/* ---------------- right viewport ---------------- */
// Cut the current camera rect out of the playing master video. Drawing a frame
// that is already decoded is free, so the follow view keeps up with playback -
// the still path costs ~270 ms per frame and always trails behind.
function drawCropFromVideo() {
  const v = $('viewVideo');
  if (!state.useVideo || v.readyState < 2 || !v.videoWidth) return false;
  const bake = state.bake;
  if (!bake || !bake.path || !bake.mon) return false;
  const p = bake.path[state.frame];
  if (!p) return false;

  const mon = bake.mon; // [x, y, w, h] in screen pixels
  // p = [cx, cy, w, h] with the centre, matching render.rs (cx - w * 0.5).
  const kx = v.videoWidth / mon[2];
  const ky = v.videoHeight / mon[3];
  let sw = p[2] * kx;
  let sh = p[3] * ky;
  let sx = (p[0] - mon[0]) * kx - sw / 2;
  let sy = (p[1] - mon[1]) * ky - sh / 2;
  sx = Math.max(0, Math.min(v.videoWidth - 2, sx));
  sy = Math.max(0, Math.min(v.videoHeight - 2, sy));
  sw = Math.max(2, Math.min(v.videoWidth - sx, sw));
  sh = Math.max(2, Math.min(v.videoHeight - sy, sh));

  const cv = $('cropCanvas');
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  const box = fitInside(w, h, sw, sh);
  ctx.drawImage(v, sx, sy, sw, sh, box.x, box.y, box.w, box.h);
  ctx.strokeStyle = 'rgba(255,255,255,.06)';
  ctx.lineWidth = 1;
  ctx.strokeRect(box.x + .5, box.y + .5, box.w - 1, box.h - 1);
  return true;
}

function drawRight() {
  const cv = $('cropCanvas');
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  // the proxy video already shows the cropped result
  if (state.proxyReady && !state.proxyStale) return;
  if (drawCropFromVideo()) return;
  if (!state.cropImg) return;
  const iw = state.cropImg.naturalWidth, ih = state.cropImg.naturalHeight;
  const box = fitInside(w, h, iw, ih);
  ctx.fillStyle = '#05070a';
  ctx.fillRect(box.x, box.y, box.w, box.h);
  ctx.drawImage(state.cropImg, box.x, box.y, box.w, box.h);
  ctx.strokeStyle = 'rgba(255,255,255,.06)';
  ctx.lineWidth = 1;
  ctx.strokeRect(box.x + .5, box.y + .5, box.w - 1, box.h - 1);
}

/* ---------------- media (video preview) ---------------- */
async function setupMedia() {
  if (!state.clip) return;
  const dir = state.clip.dir;

  try {
    const mp = await invoke('media_path', { dir, which: 'master' });
    const v = $('viewVideo');
    // Needed so the follow view can be drawn from this video without tainting
    // the canvas (a tainted canvas breaks getImageData/toDataURL).
    v.crossOrigin = 'anonymous';
    v.src = mediaUrl(mp);
    v.onloadedmetadata = () => {
      v.classList.add('is-on');
      state.useVideo = true;
      seekVideos(state.frame / (state.bake ? state.bake.fps : 30));
      drawLeft();
    };
  } catch {
    state.useVideo = false;
    $('viewVideo').classList.remove('is-on');
  }

  await loadProxy(dir);
}

async function loadProxy(dir) {
  try {
    const pp = await invoke('media_path', { dir, which: 'proxy' });
    const cv = $('cropVideo');
    // cache-buster: the proxy is rewritten when regenerated
    cv.src = mediaUrl(pp) + (mediaUrl(pp).startsWith('/media') ? '&v=' : '?v=') + Date.now();
    cv.onloadedmetadata = () => {
      cv.classList.add('is-on');
      state.proxyReady = true;
      state.proxyStale = false;
      $('btnProxy').classList.remove('is-on');
      seekVideos(state.frame / (state.bake ? state.bake.fps : 30));
      drawRight();
    };
  } catch {
    state.proxyReady = false;
    $('cropVideo').classList.remove('is-on');
  }
}

async function generateProxy() {
  if (!state.clip || state.proxyBusy) return;
  state.proxyBusy = true;
  const btn = $('btnProxy');
  btn.disabled = true;
  btn.textContent = '生成中…';
  try {
    await invoke('render_proxy', { dir: state.clip.dir, edit: editText(), height: 480 });
    await loadProxy(state.clip.dir);
    toast('预览已生成', 1600);
  } catch (e) {
    toast('生成失败: ' + e, 3000);
  } finally {
    state.proxyBusy = false;
    btn.disabled = false;
    btn.textContent = '生成预览';
  }
}

/* ---------------- timeline ---------------- */
const TL = { dragging: false, pad: 14 };

function tlGeom() {
  const cv = $('tlCanvas');
  const { ctx, w, h } = sizeCanvas(cv);
  const dur = state.clip ? state.clip.duration : 1;
  // zoom 0 = whole clip; 1 = 2x; 2 = 4x. The window follows the playhead so
  // zooming in keeps the current frame visible instead of snapping to the start.
  const span = Math.max(0.5, dur / Math.pow(2, state.zoom || 0));
  const fps = state.bake ? state.bake.fps : 30;
  const playT = state.frame / fps;
  const start = dur - span <= 0
    ? 0
    : Math.min(Math.max(0, playT - span / 2), dur - span);
  return { ctx, w, h, dur, span, start, x0: TL.pad, x1: w - TL.pad };
}

function timeToX(g, t) {
  return g.x0 + ((t - g.start) / g.span) * (g.x1 - g.x0);
}
function xToTime(g, x) {
  const t = g.start + ((x - g.x0) / (g.x1 - g.x0)) * g.span;
  return Math.max(0, Math.min(g.dur, t));
}

const TRIM_HIT = 10;

function trimHandles(g) {
  if (!state.trim) return null;
  return { a: timeToX(g, state.trim.a), b: timeToX(g, state.trim.b) };
}

function drawTimeline() {
  const g = tlGeom();
  const { ctx, w, h } = g;
  ctx.clearRect(0, 0, w, h);

  const laneY = 26;
  const laneH = h - laneY - 6;

  // ---- ruler
  ctx.strokeStyle = '#1a212c';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(g.x0, laneY - 0.5);
  ctx.lineTo(g.x1, laneY - 0.5);
  ctx.stroke();

  const step = niceStep(g.span, w / 90);
  ctx.fillStyle = '#5d6878';
  ctx.font = '10px "Segoe UI", system-ui, sans-serif';
  ctx.textBaseline = 'middle';
  for (let t = Math.floor(g.start / step) * step; t <= g.start + g.span + 1e-6; t += step) {
    if (t < g.start - 1e-6) continue;
    const x = Math.round(timeToX(g, t)) + .5;
    ctx.strokeStyle = '#232b38';
    ctx.beginPath();
    ctx.moveTo(x, laneY - 6);
    ctx.lineTo(x, laneY - 1);
    ctx.stroke();
    ctx.fillText(tc(t).replace(/^00:/, ''), x + 4, 12);
  }

  // ---- lane
  const grad = ctx.createLinearGradient(0, laneY, 0, laneY + laneH);
  grad.addColorStop(0, '#151b25');
  grad.addColorStop(1, '#11161e');
  ctx.fillStyle = grad;
  roundRect(ctx, g.x0, laneY, g.x1 - g.x0, laneH, 6);
  ctx.fill();
  ctx.strokeStyle = '#232c3a';
  ctx.stroke();

  // ---- sampling density histogram
  if (state.track.length > 1) {
    const bins = Math.max(24, Math.min(600, Math.floor(g.x1 - g.x0)));
    const { counts, peak } = histBins(g, bins);
    ctx.save();
    ctx.beginPath();
    roundRect(ctx, g.x0, laneY, g.x1 - g.x0, laneH, 6);
    ctx.clip();
    const bw = (g.x1 - g.x0) / bins;
    for (let i = 0; i < bins; i++) {
      if (!counts[i]) continue;
      const hgt = Math.max(1, (counts[i] / peak) * (laneH - 8));
      ctx.fillStyle = 'rgba(79,140,255,.22)';
      ctx.fillRect(g.x0 + i * bw, laneY + laneH - 3 - hgt, Math.max(bw, 1), hgt);
    }
    ctx.restore();
  }

  // ---- keyframe ticks
  if (state.kfs.length) {
    ctx.fillStyle = 'rgba(46,230,168,.85)';
    for (const kf of state.kfs) {
      const x = timeToX(g, kf.t);
      ctx.fillRect(x - 1, laneY + 2, 2, 7);
    }
  }

  // ---- trim region
  const hs = trimHandles(g);
  if (hs) {
    ctx.save();
    ctx.fillStyle = 'rgba(5,7,10,.55)';
    ctx.fillRect(g.x0, laneY, hs.a - g.x0, laneH);
    ctx.fillRect(hs.b, laneY, g.x1 - hs.b, laneH);
    ctx.restore();

    ctx.strokeStyle = 'rgba(46,230,168,.9)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(hs.a, laneY - 2); ctx.lineTo(hs.a, laneY + laneH + 2);
    ctx.moveTo(hs.b, laneY - 2); ctx.lineTo(hs.b, laneY + laneH + 2);
    ctx.stroke();

    // grips
    for (const x of [hs.a, hs.b]) {
      ctx.fillStyle = '#2ee6a8';
      roundRect(ctx, x - 3.5, laneY + laneH / 2 - 9, 7, 18, 3);
      ctx.fill();
    }
  }

  // ---- playhead
  const px = timeToX(g, state.frame / (state.bake ? state.bake.fps : 30));
  ctx.strokeStyle = '#4f8cff';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(px, laneY - 8);
  ctx.lineTo(px, laneY + laneH);
  ctx.stroke();
  ctx.fillStyle = '#4f8cff';
  roundRect(ctx, px - 4.5, laneY - 10, 9, 9, 3);
  ctx.fill();

  $('tcNow').textContent = tc(state.frame / (state.bake ? state.bake.fps : 30));
  const tcEl = $('trimChip');
  if (tcEl) {
    if (state.trim) {
      const kept = state.trim.b - state.trim.a;
      tcEl.style.display = '';
      tcEl.textContent = `保留 ${tc(kept)}`;
    } else {
      tcEl.style.display = 'none';
    }
  }
}

// Binning the whole track on every redraw is O(n) - with a long recording
// (250 Hz track) that is a few ms per frame at 144 Hz. The result only depends
// on the track and the visible window, so remember it.
let histCache = { track: null, start: 0, span: 0, bins: 0, counts: null, peak: 1 };

function histBins(g, bins) {
  if (
    histCache.track === state.track &&
    histCache.start === g.start &&
    histCache.span === g.span &&
    histCache.bins === bins &&
    histCache.counts
  ) {
    return histCache;
  }
  const counts = new Float32Array(bins);
  for (const t of state.track) {
    const b = Math.floor(((t[0] - g.start) / g.span) * bins);
    if (b >= 0 && b < bins) counts[b]++;
  }
  let peak = 1;
  for (let i = 0; i < bins; i++) if (counts[i] > peak) peak = counts[i];
  histCache = { track: state.track, start: g.start, span: g.span, bins, counts, peak };
  return histCache;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function niceStep(dur, target) {
  const raw = dur / Math.max(1, target);
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / pow;
  const mult = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return Math.max(0.1, mult * pow);
}

function seekTo(x) {
  const g = tlGeom();
  state.frame = Math.max(0, Math.min((state.bake ? state.bake.frames : 1) - 1,
    Math.round(xToTime(g, x) * (state.bake ? state.bake.fps : 30))));
  drawTimeline();
  drawLeft();
  scheduleStill();
}

// ---- mouse: drag trim handles, otherwise scrub
const tlCanvas = $('tlCanvas');
let tlDrag = null;
let tlDragAnchor = 0;

tlCanvas.addEventListener('mousedown', (ev) => {
  const r = tlCanvas.getBoundingClientRect();
  const x = ev.clientX - r.left;
  const g = tlGeom();
  const hs = trimHandles(g);

  if (hs) {
    if (Math.abs(x - hs.a) <= TRIM_HIT) { tlDrag = 'a'; return; }
    if (Math.abs(x - hs.b) <= TRIM_HIT) { tlDrag = 'b'; return; }
  }
  if (state.trimMode) {
    tlDrag = 'new';
    const t = xToTime(g, x);
    state.trim = { a: t, b: t };
    tlDragAnchor = t;
    drawTimeline();
    return;
  }
  tlDrag = 'seek';
  seekTo(x);
});

tlCanvas.addEventListener('dblclick', () => {
  state.trim = null;
  drawTimeline();
  drawLeft();
});

window.addEventListener('mousemove', (ev) => {
  if (!tlDrag) return;
  const r = tlCanvas.getBoundingClientRect();
  const x = ev.clientX - r.left;
  if (tlDrag === 'seek') { seekTo(x); return; }

  const g = tlGeom();
  const t = xToTime(g, x);
  const fps = state.bake ? state.bake.fps : 30;
  const minGap = 3 / fps;

  if (tlDrag === 'new') {
    state.trim = { a: Math.min(tlDragAnchor, t), b: Math.max(tlDragAnchor, t) };
    drawTimeline();
    drawLeft();
    return;
  }

  if (!state.trim) state.trim = { a: 0, b: g.dur };
  if (tlDrag === 'a') state.trim.a = Math.min(t, state.trim.b - minGap);
  else state.trim.b = Math.max(t, state.trim.a + minGap);
  state.trim.a = Math.max(0, state.trim.a);
  state.trim.b = Math.min(g.dur, state.trim.b);
  drawTimeline();
  drawLeft();
});

window.addEventListener('mouseup', () => {
  if (tlDrag === 'new' && state.trim) {
    const fps = state.bake ? state.bake.fps : 30;
    if (state.trim.b - state.trim.a < 3 / fps) state.trim = null;
    drawTimeline();
    drawLeft();
  } else if (tlDrag && tlDrag !== 'seek') {
    markTrimDirty();
  }
  tlDrag = null;
});

let trimTimer = 0;
function markTrimDirty() {
  clearTimeout(trimTimer);
  trimTimer = setTimeout(() => {
    if (state.trim && state.trim.a <= 0.001 && state.trim.b >= (state.clip ? state.clip.duration : 0) - 0.02) {
      state.trim = null;   // full range == no trim
      drawTimeline();
    }
  }, 50);
}

document.querySelectorAll('#tlZoom button').forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll('#tlZoom button').forEach((x) => x.classList.remove('is-active'));
    b.classList.add('is-active');
    state.zoom = Number(b.dataset.z);
    drawTimeline();
  };
});

/* ---------------- playback ---------------- */
let playTimer = 0;
function playVideos(on) {
  const fps = state.bake ? state.bake.fps : 30;
  if (on) {
    seekVideos(state.frame / fps);
    for (const el of [$('viewVideo'), $('cropVideo')]) {
      if (el.classList.contains('is-on')) el.play().catch(() => {});
    }
  } else {
    for (const el of [$('viewVideo'), $('cropVideo')]) {
      try { el.pause(); } catch {}
    }
  }
}

function tickVideo() {
  if (!state.playing) return;
  const v = $('viewVideo');
  const fps = state.bake ? state.bake.fps : 30;
  if (state.useVideo && v.readyState >= 2) {
    const last = (state.bake ? state.bake.frames : 1) - 1;
    state.frame = Math.max(0, Math.min(last, Math.round(v.currentTime * fps)));
    drawTimeline();
    drawLeft();
    if (!(state.proxyReady && !state.proxyStale)) drawRight();
    const c = $('cropVideo');
    if (state.proxyReady && !state.proxyStale && c.readyState >= 2 &&
        Math.abs(c.currentTime - v.currentTime) > 0.08) {
      try { c.currentTime = v.currentTime; } catch {}
    }
  }
  requestAnimationFrame(tickVideo);
}

function stopPlayback() {
  state.playing = false;
  $('icoPlay').style.display = '';
  $('icoPause').style.display = 'none';
  clearInterval(playTimer);
  playVideos(false);
}

function startPlayback() {
  state.playing = true;
  $('icoPlay').style.display = 'none';
  $('icoPause').style.display = '';
  clearInterval(playTimer);
  playVideos(true);

  if (state.useVideo) {
    tickVideo();
    return;
  }
  // fallback: no video available, drive stills on a timer
  const fps = state.bake ? state.bake.fps : 30;
  const start = performance.now();
  const startFrame = state.frame;
  playTimer = setInterval(() => {
    const dt = (performance.now() - start) / 1000;
    const f = Math.round(startFrame + dt * fps);
    const last = (state.bake ? state.bake.frames : 1) - 1;
    if (f >= last) {
      state.frame = last;
      drawTimeline();
      drawLeft();
      scheduleStill();
      onPlaybackEnd();
      return;
    }
    state.frame = f;
    drawTimeline();
    drawLeft();
    scheduleStill();
  }, 90);
}

// Both videos fire 'ended'; ignore the echo from the second one.
let lastRestart = 0;

// Rewind to the first frame without leaving the playing state.
function replayFromStart() {
  lastRestart = performance.now();
  state.frame = 0;
  for (const el of [$('viewVideo'), $('cropVideo')]) {
    if (!el.classList.contains('is-on')) continue;
    try {
      el.currentTime = 0;
      if (state.playing) el.play().catch(() => {});
    } catch {}
  }
  drawTimeline();
  drawLeft();
  if (!state.useVideo) scheduleStill();
}

function onPlaybackEnd() {
  if (!state.playing) return;
  if (performance.now() - lastRestart < 250) return;
  if (state.loop) {
    replayFromStart();
    if (!state.useVideo) startPlayback(); // the still timer needs a fresh origin
  } else {
    stopPlayback();
  }
}

$('viewVideo').addEventListener('ended', onPlaybackEnd);
$('cropVideo').addEventListener('ended', onPlaybackEnd);

$('btnPlay').onclick = () => {
  if (state.playing) {
    stopPlayback();
    return;
  }
  // pressing play while parked on the last frame replays from the head,
  // otherwise it would "play" and stop again in the same instant
  const last = (state.bake ? state.bake.frames : 1) - 1;
  if (state.frame >= last) {
    state.frame = 0;
    for (const el of [$('viewVideo'), $('cropVideo')]) {
      if (el.classList.contains('is-on')) { try { el.currentTime = 0; } catch {} }
    }
    drawTimeline();
    drawLeft();
  }
  startPlayback();
};

$('btnProxy').onclick = generateProxy;

/* ---------------- resize ---------------- */
let rzTimer = 0;
/* ---------------- draggable splits ---------------- */
// The viewports, the timeline and the params area are laid out by CSS variables,
// so dragging a handle is just a variable write. Sizes persist across runs, which
// matters because the useful split depends on the monitor.
const SPLIT_KEY = 'mc.split';

function applySplits(saved) {
  const stage = $('stageEdit');
  const vps = document.querySelector('.viewports');
  if (!stage || !vps) return;
  const rec = $('stageRecord');
  if (rec && saved.recParams) rec.style.setProperty('--rec-params-h', saved.recParams + 'px');
  if (saved.tl) stage.style.setProperty('--tl-h', saved.tl + 'px');
  if (saved.params) stage.style.setProperty('--params-h', saved.params + 'px');
  if (saved.vp) vps.style.setProperty('--vp-left', saved.vp + '%');
}

function relayout() {
  drawLeft();
  drawRight();
  drawTimeline();
}

function initSplits() {
  const stage = $('stageEdit');
  const vps = document.querySelector('.viewports');
  const timeline = document.querySelector('.timeline');
  const params = document.querySelector('.params');
  if (!stage || !vps || !timeline || !params) return;

  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(SPLIT_KEY) || '{}'); } catch {}
  applySplits(saved);

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  // two viewports: share the row width
  let vpStart = 0, vpW = 1;
  $('splitVp')?.addEventListener('pointerdown', (e) => {
    vpW = vps.getBoundingClientRect().width - 14 || 1;
    vpStart = e.clientX;
    const left = vps.querySelector('.vp').getBoundingClientRect().width;
    const pct0 = (left / vpW) * 100;
    const onMove = (ev) => {
      const pct = clamp(pct0 + ((ev.clientX - vpStart) / vpW) * 100, 22, 78);
      vps.style.setProperty('--vp-left', pct + '%');
    };
    const move = (ev) => onMove(ev);
    const up = () => {
      $('splitVp').removeEventListener('pointermove', move);
      $('splitVp').removeEventListener('pointerup', up);
      saved.vp = parseFloat(vps.style.getPropertyValue('--vp-left')) || 50;
      localStorage.setItem(SPLIT_KEY, JSON.stringify(saved));
    };
    $('splitVp').addEventListener('pointermove', move);
    $('splitVp').addEventListener('pointerup', up);
  });

  // stage rows: dragging the upper handle grows the viewports by shrinking the
  // timeline, the lower one shrinks the params area
  let rowStart = 0, tl0 = 0, params0 = 0, stageH = 0;
  const rowDrag = (id, kind) => {
    const h = $(id);
    if (!h) return;
    h.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      try { h.setPointerCapture(e.pointerId); } catch {}
      h.classList.add('dragging');
      document.body.classList.add('split-drag', 'rows');
      rowStart = e.clientY;
      tl0 = timeline.getBoundingClientRect().height;
      params0 = params.getBoundingClientRect().height;
      stageH = stage.getBoundingClientRect().height;
      const move = (ev) => {
        const dy = ev.clientY - rowStart;
        if (kind === 'tl') {
          const v = clamp(tl0 - dy, 56, Math.max(56, stageH - params0 - 160));
          stage.style.setProperty('--tl-h', Math.round(v) + 'px');
        } else {
          const v = clamp(params0 - dy, 84, Math.max(84, stageH - tl0 - 160));
          stage.style.setProperty('--params-h', Math.round(v) + 'px');
        }
        relayout();
      };
      const up = () => {
        h.removeEventListener('pointermove', move);
        h.removeEventListener('pointerup', up);
        h.removeEventListener('pointercancel', up);
        h.classList.remove('dragging');
        document.body.classList.remove('split-drag', 'rows');
        saved.tl = parseInt(stage.style.getPropertyValue('--tl-h')) || undefined;
        saved.params = parseInt(stage.style.getPropertyValue('--params-h')) || undefined;
        localStorage.setItem(SPLIT_KEY, JSON.stringify(saved));
        relayout();
      };
      h.addEventListener('pointermove', move);
      h.addEventListener('pointerup', up);
      h.addEventListener('pointercancel', up);
    });
  };
  rowDrag('splitStageA', 'tl');
  rowDrag('splitStageB', 'params');

  // recorder page: preview / control bar / params, the params panel is resizable
  const recStage = $('stageRecord');
  const recParams = recStage && recStage.querySelector('.params');
  const recHandle = $('splitRecParams');
  if (recStage && recParams && recHandle) {
    recHandle.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      try { recHandle.setPointerCapture(e.pointerId); } catch {}
      recHandle.classList.add('dragging');
      document.body.classList.add('split-drag', 'rows');
      const startY = e.clientY;
      const h0 = recParams.getBoundingClientRect().height;
      const stageH = recStage.getBoundingClientRect().height;
      const move = (ev) => {
        const v = clamp(h0 - (ev.clientY - startY), 90, Math.max(90, stageH - 170));
        recStage.style.setProperty('--rec-params-h', Math.round(v) + 'px');
      };
      const up = () => {
        recHandle.removeEventListener('pointermove', move);
        recHandle.removeEventListener('pointerup', up);
        recHandle.classList.remove('dragging');
        document.body.classList.remove('split-drag', 'rows');
        saved.recParams = parseInt(recStage.style.getPropertyValue('--rec-params-h')) || undefined;
        localStorage.setItem(SPLIT_KEY, JSON.stringify(saved));
      };
      recHandle.addEventListener('pointermove', move);
      recHandle.addEventListener('pointerup', up);
    });
  }
}

initSplits();

window.addEventListener('resize', () => {
  clearTimeout(rzTimer);
  rzTimer = setTimeout(() => {
    const active = document.querySelector('.tab.is-active');
    if (active) moveGlider(active);
    drawLeft();
    drawRight();
    drawTimeline();
  }, 60);
});

window.__mc = state;   // debug/automation handle

/* ---------------- recorder preview ---------------- */
let recPreviewTimer = 0;

async function tickRecPreview() {
  if (!state.recPreviewOn) return;
  try {
    // A data URL: writing the JPEG to a file and serving it over the asset
    // protocol was measured at 23.6 ms vs 24.6 ms, so it saves no time, and the
    // browser caches the small set of filenames so the picture stops updating.
    const url = await invoke('preview_frame');
    const img = $('recPreview');
    if (url && img.src !== url) {
      img.src = url;
      if (img.complete && img.naturalWidth) {
        $('recCropInfo').textContent = `${img.naturalWidth}×${img.naturalHeight}`;
      } else {
        img.onload = () => {
          $('recCropInfo').textContent = `${img.naturalWidth}×${img.naturalHeight}`;
        };
      }
    }
    $('recEmpty').style.display = 'none';
  } catch {}
  // While recording the preview shares the main thread with the capture and
  // encoder plumbing; 5 fps is still enough to aim the camera and costs half.
  if (state.recPreviewOn) {
    recPreviewTimer = setTimeout(tickRecPreview, state.recording ? 200 : 110);
  }
}

let monitorsLoaded = false;

function paintRecHint() {
  if (state.recording) {
    $('recHint').textContent = '正在录制 — 点击方形按钮或按快捷键停止';
    return;
  }
  const m = (state.monitors || [])[state.monitor];
  const hk = state.hotkeys && (state.hotkeys[0] || state.hotkeys[1])
    ? ` · ${state.hotkeys[1] ? 'F9' : 'Ctrl+Alt+R'} 开始/停止`
    : '';
  $('recHint').textContent = (m
    ? `${m.label} · 同时生成原片 / 跟拍 / 轨迹`
    : '主显示器 · 30 fps · 同时生成原片 / 跟拍 / 轨迹') + hk;
}

async function loadMonitors() {
  try {
    const list = await invoke('list_monitors');
    state.monitors = list || [];
    const sel = $('recMonitor');
    sel.innerHTML = state.monitors
      .map((m) => `<option value="${m.index}">${m.label}</option>`)
      .join('');
    if (state.monitor >= state.monitors.length) state.monitor = 0;
    sel.value = String(state.monitor);
    monitorsLoaded = true;
  } catch (e) {
    $('recWarn').textContent = '获取显示器列表失败: ' + e;
  }
}

async function restartPreview() {
  if (state.recording) return;
  try {
    await invoke('preview_stop');
    await invoke('preview_start', { edit: editText(), monitor: state.monitor });
  } catch (e) {
    $('recWarn').textContent = '预览启动失败: ' + e;
  }
}

async function enterRecordTab() {
  state.recPreviewOn = true;
  try {
    const on = await invoke('hud_get');
    $('hudToggle').classList.toggle('is-on', !!on);
  } catch {}
  $('recEmpty').style.display = '';
  $('recState').textContent = '待机';
  try {
    if (!monitorsLoaded) await loadMonitors();
    try {
      state.hotkeys = await invoke('hotkey_status');
    } catch {}
    if (state.nvenc === null) {
      try {
        state.nvenc = await invoke('nvenc_available');
      } catch {
        state.nvenc = false;
      }
      const box = $('recHw');
      // The saved preference decides this, not the probe: NVENC being available
      // does not mean the user wants it. It only has to be forced off when the
      // hardware cannot do it at all.
      const want = state.appSettings ? !!state.appSettings.hw : true;
      state.hw = !!state.nvenc && want;
      box.checked = state.hw;
      box.disabled = !state.nvenc;
      box.closest('.hw-chk').classList.toggle('is-off', !state.nvenc);
      if (!state.nvenc) box.closest('.hw-chk').title = '此机器未检测到可用的 NVENC';
    }
    paintRecHint();
    if (!state.recording) {
      await invoke('preview_start', { edit: editText(), monitor: state.monitor });
    }
  } catch (e) {
    $('recWarn').textContent = '预览启动失败: ' + e;
  }
  clearTimeout(recPreviewTimer);
  tickRecPreview();
}

function leaveRecordTab() {
  state.recPreviewOn = false;
  clearTimeout(recPreviewTimer);
  if (!state.recording) invoke('preview_stop').catch(() => {});
  // The frame only describes what the recorder page is previewing, so it has no
  // meaning on the editor. Leaving it on would leave a border floating over an
  // unrelated screen.
  if ($('hudToggle').classList.contains('is-on')) {
    $('hudToggle').classList.remove('is-on');
    state.hudOn = false;
    invoke('hud_set', { enabled: false }).catch(() => {});
  }
}

/* ---------------- boot ---------------- */
(async function boot() {
  loadSavedParams();
  buildParams('paramsGrid');
  buildParams('recParamsGrid');
  paintLoopToggle();
  const active = document.querySelector('.tab.is-active');
  requestAnimationFrame(() => moveGlider(active));

  const ok = await loadClips();
  if (!ok) return;

  state.frame = 0;
  await setupMedia();
  drawTimeline();
  drawLeft();
  scheduleStill();

  // preload neighbours so scrubbing feels instant
  setTimeout(() => scheduleStill(), 250);
})();

/* ---- boot: tell the watchdog the UI thread is alive ---- */
// Webview timers only run while the UI thread is pumping; a gap in these beats
// is what the Rust watchdog reports as a stall.
if (IS_TAURI) {
  setInterval(() => {
    invoke('heartbeat').catch(() => {});
  }, 2000);
}

/* ---- boot: load the saved settings before the first paint ---- */
  loadAppSettings().then((a) => {
    if (!a) {
      // one retry: the very first call can land before the IPC bridge is ready
      setTimeout(() => loadAppSettings(), 700);
      return;
    }
    state.hw = !!a.hw;
    $('hudToggle').classList.toggle('is-on', !!a.hud);
    invoke('hud_set', { enabled: !!a.hud }).catch(() => {});
  });
