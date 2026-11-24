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
  tlPan: null,          // left edge in seconds once the user pans by hand
  dragHint: null,       // {t} while a trim handle is being dragged
  clicks: [],           // times of left-button presses, for snapping
  undoStack: [],
  redoStack: [],
  edit: {
    zoom: 1.0,
    expand: 1.2,
    threshold: 3400,
    smooth: 66,
    resp: 35,
    follow: 1.0,
    look: 60,
    dz: 7,
    cs: 60,
    clk: 1,
    aspect: 0,
    width: 1080,
  },
  stillInFlight: false,
  stillPending: false,
  dirty: false,
  trims: [],            // [{a, b}, ...] kept ranges; empty = whole clip
  speeds: [],           // [{a, b, speed}, ...] speed regions, source seconds
  speedSel: -1,         // index of the region whose slider is showing
  kfs: [],              // [{t, x, y}] manual follow points
  kfMode: false,
  trimMode: false,
  speedMode: false,
  loop: false,
  monitor: 0,
  lastToggle: 0,
  hotkeys: null,
  hw: false,
  recFps: 30,           // 30 or 60; the capture rate, fixed for the whole take
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
  // Baked stills, keyed by output second. A still costs one ffmpeg decode
  // (~250 ms); replaying the same stretch would otherwise pay that again for
  // every frame. Dropped whenever the edit changes.
  stillCache: new Map(),
  stillCacheKey: '',
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
    `dz ${e.dz}`,
    `cs ${e.cs}`,
    `clk ${e.clk ? 1 : 0}`,
    `aspect ${e.aspect}`,
    `width ${e.width}`,
  ];
  for (const t of state.trims) lines.push(`trim ${t.a.toFixed(3)} ${t.b.toFixed(3)}`);
  for (const v of state.speeds) lines.push(`speed ${v.a.toFixed(3)} ${v.b.toFixed(3)} ${v.speed.toFixed(3)}`);
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
    : `主显示器 · ${state.recFps} fps · 同时生成原片 / 跟拍 / 轨迹`;
  $('recState').textContent = on ? '录制中' : '待机';
  // The badge lives in the tab bar, so it stays visible on the edit tab:
  // recording is a global state, not a property of one page.
  const badge = $('recBadge');
  if (badge) {
    badge.classList.toggle('is-hidden', !on);
    if (!on) $('recBadgeTime').textContent = '00:00';
  }
  const sel = $('recMonitor');
  if (sel) sel.disabled = on;
  // The rate is fixed for the whole take, so it cannot change mid-recording.
  const fpsSel = $('recFps');
  if (fpsSel) fpsSel.disabled = on;
  paintRecHint();
  if (on) {
    state.recTimer = setInterval(async () => {
      try {
        const st = await invoke('record_status');
        if (st && st.recording) {
          $('recTime').textContent = fmtRecTime(st.elapsed);
          const bt = $('recBadgeTime');
          if (bt) bt.textContent = fmtRecTime(st.elapsed);
        }
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
        audioSystem: $('recAudioSys') ? $('recAudioSys').checked : false,
        audioMic: $('recAudioMic') ? $('recAudioMic').checked : false,
        fps: state.recFps,
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
      // Check the take before leaving: a frozen opening or a drifting audio
      // track is invisible until someone watches it, and by then it is too late
      // to simply record again.
      probeJustRecorded();
      document.querySelector('.tab[data-tab="edit"]').click();
    } catch (e) {
      setRecording(false);
      $('recWarn').textContent = '停止失败: ' + e;
    }
  }
}

// Runs the health report on the take that just finished and surfaces anything
// that would make it look wrong. Silent when the take is clean.
async function probeJustRecorded() {
  const dir = state.recDir;
  if (!dir) return;
  try {
    const report = await invoke('probe_clip', { dir });
    if (report && !report.good && report.issues && report.issues.length) {
      const line = report.issues.join('；');
      $('recWarn').textContent = '这段素材有问题：' + line;
      toast('录制完成，但' + line, 6000);
      logUi('warn', `体检: ${line} (${dir})`);
    } else if (report) {
      logUi('info', `体检通过: ${report.frames} 帧 / 补帧 ${report.duplicates}`);
    }
  } catch (e) {
    logUi('error', `体检失败: ${e}`);
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

// The viewport cannot be larger than the screen, so on a small monitor the zoom
// slider stops doing anything. Say so instead of letting the take surprise you.
let fitTimer = 0;
function updateFitHint() {
  clearTimeout(fitTimer);
  fitTimer = setTimeout(async () => {
    const el = $('recFitWarn');
    if (!el || !IS_TAURI) return;
    try {
      const fit = await invoke('viewport_fit', { edit: editText(), monitor: state.monitor });
      if (fit && fit.limited) {
        el.classList.remove('is-hidden');
        el.textContent = `缩放受限 ${fit.effective_zoom.toFixed(2)}×`;
        el.title = `屏幕 ${fit.monitor[2]}×${fit.monitor[3]} 放不下 ${Math.round(
          fit.requested[0]
        )}×${Math.round(fit.requested[1])} 的视口，实际为 ${Math.round(fit.actual[0])}×${Math.round(
          fit.actual[1]
        )}`;
      } else {
        el.classList.add('is-hidden');
      }
    } catch {}
  }, 120);
}

$('recHw').onchange = () => {
  state.hw = $('recHw').checked;
};

// Audio switches save themselves: they are a capture preference, not part of the
// clip, so there is nothing to re-bake when they change.
async function saveAudioPrefs() {
  const st = state.appSettings;
  if (!st) return;
  try {
    await invoke('set_app_settings', {
      capturesDir: st.configured || '',
      hw: !!st.hw,
      hud: !!st.hud,
      verbose: !!st.verbose,
      audioSystem: $('recAudioSys') ? $('recAudioSys').checked : false,
      audioMic: $('recAudioMic') ? $('recAudioMic').checked : false,
    });
    st.audioSys = $('recAudioSys') ? $('recAudioSys').checked : false;
    st.audioMic = $('recAudioMic') ? $('recAudioMic').checked : false;
  } catch (e) {
    logUi('error', `保存音频开关失败: ${e}`);
    toast('音频开关未能保存');
  }
}

// The capture rate survives a restart: it belongs to the machine, not to one
// take, and a 60 fps habit should not have to be re-chosen every launch.
try {
  state.recFps = Number(localStorage.getItem('mc.recFps')) === 60 ? 60 : 30;
} catch {}
{
  const fpsSel = $('recFps');
  if (fpsSel) {
    fpsSel.value = String(state.recFps);
    fpsSel.onchange = () => {
      state.recFps = Number(fpsSel.value) === 60 ? 60 : 30;
      try { localStorage.setItem('mc.recFps', String(state.recFps)); } catch {}
      paintRecHint();
    };
  }
}

for (const id of ['recAudioSys', 'recAudioMic']) {
  const box = $(id);
  if (box) box.onchange = saveAudioPrefs;
}

$('recMonitor').onchange = async (ev) => {
  state.monitor = Number(ev.target.value) || 0;
  paintRecHint();
  updateFitHint();
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
    const [effective, configured, hw, hud, verbose, audioSys, audioMic] = await invoke('app_settings');
    state.appSettings = { effective, configured, hw, hud, verbose, audioSys, audioMic };
    const sysBox = $('recAudioSys');
    const micBox = $('recAudioMic');
    if (sysBox) sysBox.checked = !!audioSys;
    if (micBox) micBox.checked = !!audioMic;
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
    await invoke('set_app_settings', {
      capturesDir: dir,
      hw,
      hud,
      verbose,
      audioSystem: $('recAudioSys') ? $('recAudioSys').checked : false,
      audioMic: $('recAudioMic') ? $('recAudioMic').checked : false,
    });
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
  { key: 'dz', label: '稳定死区', min: 0, max: 15, step: 1, fmt: (v) => Math.round(v) + '%' },
  { key: 'cs', label: '光标平滑', min: 0, max: 250, step: 5, fmt: (v) => Math.round(v) + ' ms' },
  { key: 'clk', label: '点击强调', type: 'check' },
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

    if (p.type === 'check') {
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'row-check';
      cb.checked = !!state.edit[p.key];
      cb.onchange = () => {
        pushUndo();
        state.edit[p.key] = cb.checked ? 1 : 0;
        onParamChanged();
      };
      row.appendChild(cb);
      grid.appendChild(row);
      continue;
    }

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
      // one undo step per drag, captured before the value moves
      inp.onpointerdown = () => pushUndo();
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

// ---------- undo / redo ----------
// A snapshot of everything an edit can touch. Strings keep it trivial to
// compare and impossible to get subtly wrong in the way per-action inverses are.
function editState() {
  return JSON.stringify({ trims: state.trims, speeds: state.speeds, kfs: state.kfs, edit: state.edit });
}

function pushUndo() {
  const snap = editState();
  if (state.undoStack.length && state.undoStack[state.undoStack.length - 1] === snap) return;
  state.undoStack.push(snap);
  if (state.undoStack.length > 80) state.undoStack.shift();
  state.redoStack.length = 0;
}

function applyEditState(json) {
  const o = JSON.parse(json);
  state.trims = o.trims || [];
  state.speeds = o.speeds || [];
  state.speedSel = -1;
  syncSpeedControls();
  state.kfs = o.kfs || [];
  Object.assign(state.edit, o.edit || {});
  buildParams('paramsGrid');
  buildParams('recParamsGrid');
  drawTimeline();
  drawLeft();
  onParamChanged();
}

function undo() {
  if (!state.undoStack.length) {
    toast('没有可撤销的操作');
    return;
  }
  state.redoStack.push(editState());
  applyEditState(state.undoStack.pop());
}

function redo() {
  if (!state.redoStack.length) return;
  state.undoStack.push(editState());
  applyEditState(state.redoStack.pop());
}

// Puts a clip's stored edit back into the UI. Values come out of the engine
// already resolved (mcl > meta), so the sliders show what the take really used.
function applyLoadedEdit(st) {
  Object.assign(state.edit, {
    zoom: st.zoom,
    expand: st.expand,
    threshold: st.threshold,
    smooth: st.smooth,
    resp: st.resp,
    follow: st.follow,
    look: st.look,
    aspect: st.aspect,
    width: st.width,
    dz: st.dz,
    cs: st.cs,
    clk: st.clk,
  });
  state.trims = (st.trims || []).map(([a, b]) => ({ a, b }));
  state.speeds = (st.speeds || []).map(([a, b, speed]) => ({ a, b, speed }));
  state.speedSel = -1;
  syncSpeedControls();
  state.kfs = (st.kfs || []).map(([t, x, y]) => ({ t, x, y }));
  buildParams('paramsGrid');
  buildParams('recParamsGrid');
  saveParams();
}

// ---------- 3. 写回去（防抖，避免拖动时每帧写盘） ----------
let saveEditTimer = 0;
function scheduleSaveEdit() {
  if (!state.clip) return;
  clearTimeout(saveEditTimer);
  saveEditTimer = setTimeout(() => {
    if (!state.clip) return;
    invoke('save_edit', { dir: state.clip.dir, text: editText() }).catch(() => {});
  }, 500);
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
  scheduleSaveEdit();
  updateFitHint();
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
  // dragging the timeline can only mean one thing at a time
  if (state.trimMode && state.speedMode) {
    state.speedMode = false;
    $('speedToggle').classList.remove('is-on');
  }
  document.getElementById('tlCanvas').style.cursor =
    state.trimMode || state.speedMode ? 'crosshair' : '';
  if (state.trimMode) {
    toast('拖动框选要保留的区间；可多段，双击某段删除', 3000);
  }
  drawTimeline();
};

$('btnTrimClear').onclick = () => {
  pushUndo();
  state.trims = [];
  scheduleSaveEdit();
  drawTimeline();
  drawLeft();
};

$('speedToggle').onclick = () => {
  state.speedMode = !state.speedMode;
  $('speedToggle').classList.toggle('is-on', state.speedMode);
  // the two modes own the same drag gesture, so only one can be armed
  if (state.speedMode && state.trimMode) {
    state.trimMode = false;
    $('trimToggle').classList.remove('is-on');
  }
  const cv = document.getElementById('tlCanvas');
  cv.style.cursor = state.speedMode ? 'crosshair' : state.trimMode ? 'crosshair' : '';
  if (state.speedMode) {
    toast('拖动框选变速区间，再用速度下拉调整；双击某段删除', 3400);
  }
  drawTimeline();
};

$('speedPick').onchange = (e) => setSpeed(Number(e.target.value));

$('btnSpeedClear').onclick = () => {
  if (!state.speeds.length) return;
  pushUndo();
  state.speeds = [];
  state.speedSel = -1;
  syncSpeedControls();
  scheduleSaveEdit();
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

$('exStop').onclick = () => {
  invoke('export_cancel').catch(() => {});
  $('exStop').disabled = true;
  setTimeout(() => { $('exStop').disabled = false; }, 1200);
};

$('exGo').onclick = async () => {
  if (!state.clip) return;
  const btn = $('exGo');
  const stopBtn = $('exStop');
  const openedAt = Date.now();
  btn.disabled = true;
  btn.textContent = '导出中…';
  stopBtn.classList.remove('is-hidden');
  $('exProgress').classList.remove('is-hidden');
  $('exBarFill').style.width = '0%';
  $('exPercent').textContent = '0%';
  $('exFrames').textContent = '';
  $('btnExport').disabled = true;
  $('btnExport').textContent = '导出中…';

  const poll = setInterval(async () => {
    try {
      const p = await invoke('export_progress');
      if (!p || !p.active) return;
      const pct = p.total > 0 ? Math.round((p.done / p.total) * 100) : 0;
      $('exBarFill').style.width = pct + '%';
      $('exPercent').textContent = pct + '%';
      $('exFrames').textContent = p.total ? `${p.done} / ${p.total} 帧` : '';
    } catch {}
  }, 250);

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
    const msg = String(e);
    toast(msg.includes('取消') ? '已取消导出' : '导出失败: ' + msg, 5000);
  } finally {
    clearInterval(poll);
    stopBtn.classList.add('is-hidden');
    $('exProgress').classList.add('is-hidden');
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
  clearStillCache();
  $('monInfo').textContent = `${c.mon_w}×${c.mon_h} · ${c.fps}fps`;
  $('tcTotal').textContent = tc(c.duration);
  state.track = await invoke('track_points', { dir: c.dir });
  // press moments, for snapping cuts onto them
  {
    const clicks = [];
    let down = false;
    for (const q of state.track) {
      const now = (Math.floor(q[3] || 0) & 1) === 1;
      if (now && !down) clicks.push(q[0]);
      down = now;
    }
    state.clicks = clicks;
  }
  state.tlPan = null;
  state.proxyReady = false;
  state.proxyStale = false;
  // The take carries its own edit (`edit.mcl`), which is also what mc-render
  // reads; meta.json is the fallback for a clip that was never edited.
  state.trims = [];
  state.speeds = [];
  state.speedSel = -1;
  syncSpeedControls();
  state.kfs = [];
  try {
    const st = await invoke('load_edit', { dir: c.dir });
    if (st) applyLoadedEdit(st);
  } catch {}
  state.undoStack.length = 0;
  state.redoStack.length = 0;
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
    const empty = $('editEmpty');
    if (empty) empty.classList.remove('is-hidden');
    return false;
  }
  const empty = $('editEmpty');
  if (empty) empty.classList.add('is-hidden');
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

// `t` is a SOURCE second. The master sits on that clock; the proxy is a baked
// timeline in OUTPUT seconds, so it needs the matching output position - passing
// the source second to both is what made a sped-up proxy show the wrong frame.
function seekVideos(t) {
  const v = $('viewVideo');
  const c = $('cropVideo');
  if (v.classList.contains('is-on') && Math.abs(v.currentTime - t) > 0.02) {
    try { v.currentTime = t; } catch {}
  }
  if (c.classList.contains('is-on') && playingWithProxy()) {
    const o = srcToOut(t);
    if (Math.abs(c.currentTime - o) > 0.02) {
      try { c.currentTime = o; } catch {}
    }
  }
}

// Anything that changes what a still would look like invalidates the cache.
function stillCacheKey() {
  return [
    state.clip ? state.clip.dir : '',
    editText(),
    state.bake ? `${state.bake.frames}:${state.bake.fps}` : '',
  ].join('\n');
}

function clearStillCache() {
  state.stillCache.clear();
  state.stillCacheKey = '';
}

const STILL_CACHE_MAX = 400;

// The cache is keyed on the OUTPUT second, not the frame: that is the clock the
// user scrubs on, and it is the same position a replay comes back to.
function stillBucket() {
  const fps = state.bake ? state.bake.fps : 30;
  const outT = srcToOut(state.frame / fps);
  return Math.round(outT * fps);
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

  const key = stillCacheKey();
  if (key !== state.stillCacheKey) {
    clearStillCache();
    state.stillCacheKey = key;
  }

  // A frame already baked for this edit draws straight from memory. A
  // prefetched entry may carry only the crop, so a viewport that needs the
  // full frame falls through to a fresh render instead of showing a blank.
  const hit = state.stillCache.get(stillBucket());
  if (hit) {
    state.viewImg = hit.view;
    state.cropImg = hit.crop;
    drawLeft();
    drawRight();
    return;
  }

  state.stillPending = true;
  // A new position outranks the speculative fill: drop whatever it was baking.
  prefetchToken++;
  if (state.stillInFlight) return;
  state.stillInFlight = true;
  runStillQueue();
}

// Bakes one still and files it under its bucket. Shared by the on-demand path
// and the prefetcher, so a frame fetched ahead of the playhead lands in the same
// place one fetched on demand would.
async function bakeStill(bucket) {
  const cached = state.stillCache.get(bucket);
  if (cached) return cached;
  const [view, crop] = await Promise.all([fetchStill('view', 900), fetchStill('crop', 620)]);
  const [vi, ci] = await Promise.all([loadImg(view), loadImg(crop)]);
  if (state.stillCache.size >= STILL_CACHE_MAX) {
    const oldest = state.stillCache.keys().next().value;
    state.stillCache.delete(oldest);
  }
  const entry = { view: vi, crop: ci };
  state.stillCache.set(bucket, entry);
  return entry;
}

// Dragging the playhead asks for many frames in a row. Decoding them one at a
// time never keeps up, so after the visible one lands we idle-fill the frames
// either side of it: the next drag over the same stretch is then instant.
//
// The fill yields the moment the user moves the playhead again, so it can never
// starve what the eye is waiting for.
const PREFETCH_SPAN = 12;
let prefetchToken = 0;

async function prefetchAround(bucket) {
  const token = ++prefetchToken;
  const lastFrame = (state.bake ? state.bake.frames : 1) - 1;
  for (let d = 1; d <= PREFETCH_SPAN; d++) {
    if (token !== prefetchToken || state.playing || state.stillPending || !state.clip) return;
    for (const dir of [d, -d]) {
      const f = bucket + dir;
      if (f < 0 || f > lastFrame || state.stillCache.has(f)) continue;
      if (token !== prefetchToken || state.playing || state.stillPending) return;
      try {
        await bakeStill(f);
      } catch {
        /* a prefetch that fails is not worth reporting */
      }
    }
  }
}

async function runStillQueue() {
  try {
    while (state.stillPending && state.clip) {
      state.stillPending = false;
      const f = state.frame;
      const bucket = stillBucket();
      const cached = state.stillCache.get(bucket);
      if (cached) {
        state.viewImg = cached.view;
        state.cropImg = cached.crop;
        drawLeft();
        drawRight();
        continue;
      }
      try {
        const entry = await bakeStill(bucket);
        if (Math.abs(f - state.frame) < 2) {
          state.viewImg = entry.view;
          state.cropImg = entry.crop;
        }
        drawLeft();
        drawRight();
        // Fill the neighbourhood in the background. Awaiting it here would hold
        // the queue for seconds, so a drag during the fill would find the pane
        // frozen on a stale frame.
        if (!state.stillPending) prefetchAround(bucket);
      } catch (e) {
        /* seek/decode race — ignore */
      }
    }
  } finally {
    state.stillInFlight = false;
    // A request that arrived while the queue was winding down would otherwise
    // leave the pane blank until the next scrub.
    if (state.stillPending && state.clip) {
      state.stillInFlight = true;
      runStillQueue();
    }
  }
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
// Older masters contain no pointer. Reconstruct an arrow from the recorded
// trace, using the same keyframe interval and interpolation as edit::cursor_at.
function drawReplayCursor(ctx, box, source, growth = 1, edited = false) {
  if (state.clip?.pointer_in_master) return;
  const t = state.frame / (state.bake ? state.bake.fps : 30);
  const kfs = state.kfs;
  const track = edited && kfs.length >= 2 && t >= kfs[0].t && t <= kfs[kfs.length - 1].t
    ? kfs.map(k => [k.t, k.x, k.y]) : state.track;
  if (!track.length) return;
  let lo = 0, hi = track.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (track[mid][0] <= t) lo = mid; else hi = mid;
  }
  const a = track[lo], b = track[hi];
  const f = b[0] > a[0] ? Math.max(0, Math.min(1, (t - a[0]) / (b[0] - a[0]))) : 0;
  const x = a[1] + (b[1] - a[1]) * f;
  const y = a[2] + (b[2] - a[2]) * f;
  const scale = box.w / source[2];
  ctx.save();
  ctx.beginPath();
  ctx.rect(box.x, box.y, box.w, box.h);
  ctx.clip();
  ctx.translate(box.x + (x - source[0]) * scale, box.y + (y - source[1]) * box.h / source[3]);
  ctx.scale(scale * growth, scale * growth);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.lineTo(0, 22);
  ctx.lineTo(6, 16);
  ctx.lineTo(10, 25);
  ctx.lineTo(14, 23);
  ctx.lineTo(10, 14);
  ctx.lineTo(19, 14);
  ctx.closePath();
  ctx.fillStyle = '#fff';
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

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

  drawReplayCursor(ctx, box, mon);

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
    pushUndo();
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
  const source = [mon[0] + sx / kx, mon[1] + sy / ky, sw / kx, sh / ky];
  const rest = state.edit.width / Math.max(0.1, Math.min(8, state.edit.zoom));
  const growth = Math.max(1, Math.min(4, source[2] / rest));
  drawReplayCursor(ctx, box, source, growth, true);
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
    : state.tlPan !== null
      ? Math.min(Math.max(0, state.tlPan), dur - span)
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

// Pixel edges for every kept range, in the same order as `state.trims`.
function trimEdges(g) {
  return state.trims.map((t) => ({ a: timeToX(g, t.a), b: timeToX(g, t.b) }));
}

// Keeps the ranges ordered, inside the clip and free of overlaps, so the
// engine sees a sane list however the pointer was dragged.
function normalizeTrims() {
  const dur = state.clip ? state.clip.duration : Infinity;
  const fps = state.bake ? state.bake.fps : 30;
  const minGap = 3 / fps;
  const list = state.trims
    .map((t) => ({ a: Math.max(0, Math.min(t.a, t.b)), b: Math.min(dur, Math.max(t.a, t.b)) }))
    .filter((t) => t.b - t.a >= minGap)
    .sort((x, y) => x.a - y.a);
  const merged = [];
  for (const t of list) {
    const last = merged[merged.length - 1];
    if (last && t.a <= last.b + 1e-6) {
      last.b = Math.max(last.b, t.b);
    } else {
      merged.push({ a: t.a, b: t.b });
    }
  }
  state.trims = merged;
}

// Total kept seconds.
function trimTotal() {
  return state.trims.reduce((sum, t) => sum + Math.max(0, t.b - t.a), 0);
}

/* ---------------- speed regions ---------------- */
const SPEED_MIN = 0.25;
const SPEED_MAX = 4;

// Pixel edges for every speed region, in the same order as `state.speeds`.
function speedEdges(g) {
  return state.speeds.map((v) => ({ a: timeToX(g, v.a), b: timeToX(g, v.b) }));
}

// Where the little minus badge sits for a region, or null when the box is too
// narrow to hold one without covering the label.
const SPEED_DEL_R = 6;
const SPEED_DEL_INSET = 11;
function speedDeleteSpot(g, i, laneY) {
  const e = speedEdges(g)[i];
  if (!e) return null;
  if (e.b - e.a < SPEED_DEL_INSET + SPEED_DEL_R + 3) return null;
  return { x: e.a + SPEED_DEL_INSET, y: laneY + SPEED_DEL_INSET };
}

function deleteSpeedRegion(i) {
  if (i < 0 || i >= state.speeds.length) return;
  pushUndo();
  state.speeds.splice(i, 1);
  if (state.speedSel === i) state.speedSel = -1;
  else if (state.speedSel > i) state.speedSel--;
  normalizeSpeeds();
  syncSpeedControls();
  drawTimeline();
  drawLeft();
  markTrimDirty();
}

// Sorted, inside the clip and free of overlaps, so the engine sees a sane list.
// The newer region keeps its span and takes over from where the older one ends.
function normalizeSpeeds() {
  const dur = state.clip ? state.clip.duration : Infinity;
  const fps = state.bake ? state.bake.fps : 30;
  const minGap = 3 / fps;
  const list = state.speeds
    .map((v) => ({
      a: Math.max(0, Math.min(v.a, v.b)),
      b: Math.min(dur, Math.max(v.a, v.b)),
      speed: Math.max(SPEED_MIN, Math.min(SPEED_MAX, Number(v.speed) || 1)),
    }))
    .filter((v) => v.b - v.a >= minGap)
    .sort((x, y) => x.a - y.a);
  const merged = [];
  for (const v of list) {
    const last = merged[merged.length - 1];
    if (last && v.a < last.b - 1e-6) {
      if (v.b > last.b) merged.push({ a: last.b, b: v.b, speed: v.speed });
    } else {
      merged.push(v);
    }
  }
  state.speeds = merged;
  if (state.speedSel >= merged.length) state.speedSel = merged.length - 1;
}

function speedTotal() {
  return state.speeds.reduce((sum, v) => sum + Math.max(0, v.b - v.a), 0);
}

// Plain speed at a source second, regions assumed non-overlapping.
function speedRate(t) {
  for (const v of state.speeds) if (t >= v.a && t < v.b) return v.speed;
  return 1;
}

// Kept ranges in source seconds, in play order.
function keptSegs() {
  const dur = state.clip ? state.clip.duration : 0;
  return state.trims.length
    ? state.trims.map((t) => ({ a: t.a, b: t.b }))
    : [{ a: 0, b: dur }];
}

// Every stretch of the timeline with one constant speed, as
// {o: output start, a, b: source span, speed}. Both the preview clock and the
// duration estimate walk this, so they cannot drift apart.
function timelinePieces() {
  const fps = state.bake ? state.bake.fps : 30;
  const pieces = [];
  let o = 0;
  for (const s of keptSegs()) {
    if (s.b <= s.a) continue;
    const cuts = [s.a];
    for (const v of state.speeds) {
      if (v.a > s.a && v.a < s.b) cuts.push(v.a);
      if (v.b > s.a && v.b < s.b) cuts.push(v.b);
    }
    cuts.push(s.b);
    cuts.sort((x, y) => x - y);
    for (let i = 0; i < cuts.length - 1; i++) {
      const x = cuts[i], y = cuts[i + 1];
      if (y - x < 1 / fps) continue;
      const speed = speedRate((x + y) / 2);
      pieces.push({ o, a: x, b: y, speed });
      o += (y - x) / speed;
    }
  }
  return pieces;
}

// Mirrors edit::source_time_at: where an output second lands on the source.
function speedDuration() {
  const p = timelinePieces();
  return p.length ? p[p.length - 1].o + (p[p.length - 1].b - p[p.length - 1].a) / p[p.length - 1].speed : 0;
}

// Output second -> source second, and back. These are what make the preview
// play at the speed the export will use.
function outToSrc(outT) {
  const p = timelinePieces();
  if (!p.length) return outT;
  for (const q of p) {
    const len = (q.b - q.a) / q.speed;
    if (outT < q.o + len || q === p[p.length - 1]) {
      return Math.min(q.b, Math.max(q.a, q.a + Math.max(0, outT - q.o) * q.speed));
    }
  }
  return p[p.length - 1].b;
}

// Source second -> output second. Used when the clock is the raw video's own
// currentTime (no proxy to bake the speed into).
function srcToOut(srcT) {
  const p = timelinePieces();
  if (!p.length) return srcT;
  for (const q of p) {
    if (srcT < q.b || q === p[p.length - 1]) {
      return q.o + Math.max(0, Math.min(srcT, q.b) - q.a) / q.speed;
    }
  }
  const q = p[p.length - 1];
  return q.o + (q.b - q.a) / q.speed;
}

// The baked proxy already carries trims and speeds; the raw master does not.
function playingWithProxy() {
  return state.proxyReady && !state.proxyStale;
}


// Shows or hides the per-region speed picker and the summary chip.
function syncSpeedControls() {
  const chip = $('speedChip');
  const pick = $('speedPick');
  const clear = $('btnSpeedClear');
  const any = state.speeds.length > 0;
  if (chip) {
    chip.style.display = any ? '' : 'none';
    if (any) {
      const n = state.speeds.length;
      chip.textContent = `变速 ${n} 段 · 成片 ${tc(speedDuration())}`;
    }
  }
  if (clear) clear.style.display = any ? '' : 'none';
  if (pick) {
    const sel = state.speeds[state.speedSel];
    pick.style.display = sel ? '' : 'none';
    if (sel) pick.value = String(sel.speed);
  }
}

// Applies a speed to the selected region (or to the one under the playhead).
function setSpeed(v) {
  const i = state.speedSel >= 0 ? state.speedSel : speedUnderPlayhead();
  if (i < 0) return;
  pushUndo();
  state.speeds[i].speed = Math.max(SPEED_MIN, Math.min(SPEED_MAX, v));
  state.speedSel = i;
  syncSpeedControls();
  drawTimeline();
  drawLeft();
  markTrimDirty();
}

function speedUnderPlayhead() {
  const fps = state.bake ? state.bake.fps : 30;
  const t = state.frame / fps;
  return state.speeds.findIndex((v) => t >= v.a && t <= v.b);
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

  // ---- trim regions
  const edges = trimEdges(g);
  if (edges.length) {
    ctx.save();
    // everything is dimmed, then each kept range is lit back up
    ctx.fillStyle = 'rgba(5,7,10,.55)';
    ctx.fillRect(g.x0, laneY, g.x1 - g.x0, laneH);
    ctx.fillStyle = 'rgba(46,230,168,.10)';
    for (const e of edges) {
      ctx.fillRect(e.a, laneY, Math.max(1, e.b - e.a), laneH);
    }
    ctx.restore();

    ctx.strokeStyle = 'rgba(46,230,168,.9)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (const e of edges) {
      ctx.moveTo(e.a, laneY - 2); ctx.lineTo(e.a, laneY + laneH + 2);
      ctx.moveTo(e.b, laneY - 2); ctx.lineTo(e.b, laneY + laneH + 2);
    }
    ctx.stroke();

    // Grips are only draggable in 裁切 mode, so they are drawn dim otherwise:
    // a full-strength handle that ignores the pointer reads as broken.
    const live = state.trimMode;
    for (const x of edges.flatMap((e) => [e.a, e.b])) {
      ctx.fillStyle = live ? '#2ee6a8' : 'rgba(46,230,168,.32)';
      roundRect(ctx, x - 3.5, laneY + laneH / 2 - 9, 7, 18, 3);
      ctx.fill();
    }
  }

  // ---- speed regions (drawn above the trim tint, below the playhead)
  const se = speedEdges(g);
  if (se.length) {
    ctx.save();
    for (let i = 0; i < se.length; i++) {
      const speed = state.speeds[i].speed;
      const fast = speed >= 1;
      const heat = Math.min(1, Math.abs(Math.log2(speed)) / 2);
      const w = Math.max(1, se[i].b - se[i].a);
      const sel = i === state.speedSel;
      const hue = fast ? '255,176,79' : '120,180,255';
      ctx.fillStyle = `rgba(${hue},${0.10 + 0.16 * heat})`;
      ctx.fillRect(se[i].a, laneY, w, laneH);

      if (sel) {
        // a soft halo so the selected region reads at a glance
        ctx.strokeStyle = `rgba(${hue},.30)`;
        ctx.lineWidth = 6;
        ctx.strokeRect(se[i].a - 1, laneY + .5, w + 2, laneH - 1);
      }
      ctx.strokeStyle = `rgba(${hue},${sel ? 1 : 0.7})`;
      ctx.lineWidth = sel ? 2 : 1.4;
      ctx.strokeRect(se[i].a + .5, laneY + .5, w - 1, laneH - 1);

      // the factor, when the span is wide enough to hold the label
      const del = speedDeleteSpot(g, i, laneY);
      const labelShift = del ? SPEED_DEL_R * 2 + 2 : 0;
      if (se[i].b - se[i].a > 34 + labelShift) {
        ctx.font = '10px "Segoe UI", system-ui, sans-serif';
        ctx.fillStyle = fast ? 'rgba(255,205,150,.95)' : 'rgba(185,215,255,.95)';
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'center';
        ctx.fillText(`${speed}×`, (se[i].a + se[i].b + labelShift) / 2, laneY + laneH - 10);
        ctx.textAlign = 'start';
      }

      // per-region remove button: 清除变速 still drops them all, this drops one
      if (del) {
        ctx.beginPath();
        ctx.arc(del.x, del.y, SPEED_DEL_R, 0, Math.PI * 2);
        ctx.fillStyle = sel ? `rgba(${hue},.95)` : 'rgba(12,16,22,.72)';
        ctx.fill();
        ctx.strokeStyle = sel ? 'rgba(12,16,22,.55)' : `rgba(${hue},.85)`;
        ctx.lineWidth = 1.2;
        ctx.stroke();
        ctx.strokeStyle = sel ? '#0a0d12' : `rgba(${hue},1)`;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(del.x - 2.6, del.y);
        ctx.lineTo(del.x + 2.6, del.y);
        ctx.stroke();
      }
    }
    ctx.restore();
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

  // while a trim handle is dragged, name the frame it is parked on
  if (state.dragHint) {
    const txt = tc(state.dragHint.t);
    const hx = timeToX(g, state.dragHint.t);
    ctx.font = '11px "Segoe UI", system-ui, sans-serif';
    const tw = ctx.measureText(txt).width + 12;
    let bx = hx - tw / 2;
    bx = Math.max(2, Math.min(bx, w - tw - 2));
    ctx.fillStyle = 'rgba(79,140,255,.95)';
    roundRect(ctx, bx, 1, tw, 17, 4);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(txt, bx + tw / 2, 9.5);
    ctx.textAlign = 'start';
  }

  $('tcNow').textContent = tc(state.frame / (state.bake ? state.bake.fps : 30));
  const tin = $('trimIn');
  const tout = $('trimOut');
  if (tin && tout) {
    const first = state.trims[0];
    const on = !!first;
    tin.style.opacity = on ? '' : '0.35';
    tout.style.opacity = on ? '' : '0.35';
    tin.textContent = tc(on ? first.a : 0);
    tout.textContent = tc(on ? first.b : (state.clip ? state.clip.duration : 0));
  }
  const tcEl = $('trimChip');
  if (tcEl) {
    if (state.trims.length) {
      tcEl.style.display = '';
      const n = state.trims.length;
      tcEl.textContent = `保留 ${tc(trimTotal())}` + (n > 1 ? ` · ${n} 段` : '');
    } else {
      tcEl.style.display = 'none';
    }
  }
  syncSpeedControls();
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
  seekToTime(xToTime(tlGeom(), x));
}

/// Move the playhead to a time and refresh everything that shows it.
function seekToTime(t, opts) {
  const fps = state.bake ? state.bake.fps : 30;
  const last = (state.bake ? state.bake.frames : 1) - 1;
  state.frame = Math.max(0, Math.min(last, Math.round(t * fps)));
  if (state.useVideo && !(opts && opts.keepVideos)) {
    seekVideos(state.frame / fps);
  }
  drawTimeline();
  drawLeft();
  if (!(opts && opts.noStill)) scheduleStill();
}

/// Round a time to the nearest frame, or to a click when one is close enough.
///
/// A recording's "start of the interesting part" is usually a press, so snapping
/// there means the cut lands exactly on the click instead of a few pixels off.
function snapTime(t) {
  const fps = state.bake ? state.bake.fps : 30;
  const g = tlGeom();
  const pxPerSec = (g.x1 - g.x0) / Math.max(g.span, 1e-6);
  const tol = 9 / pxPerSec;
  // A press wins over a frame boundary even when the boundary is a pixel
  // closer: the point of the snap is to land the cut on the click.
  let best = null;
  let bestD = tol;
  for (const c of state.clicks) {
    const d = Math.abs(t - c);
    if (d <= bestD) {
      best = c;
      bestD = d;
    }
  }
  if (best !== null) return best;
  return Math.round(t * fps) / fps;
}

// ---- mouse: drag trim handles, otherwise scrub
const tlCanvas = $('tlCanvas');
let tlDrag = null;
let tlDragAnchor = 0;

let panAnchorX = 0;
let panStart = 0;

tlCanvas.addEventListener('mousedown', (ev) => {
  const r = tlCanvas.getBoundingClientRect();
  const x = ev.clientX - r.left;
  const g = tlGeom();

  // middle button drags the window sideways, so a long clip can be inspected
  // at a zoom level where one pixel is one frame
  if (ev.button === 1) {
    ev.preventDefault();
    tlDrag = { kind: 'pan' };
    panAnchorX = x;
    panStart = g.start;
    return;
  }

  // The minus badge wins over everything: it is small and sits inside the box,
  // and it stays live outside 变速 mode.
  {
    const y = ev.clientY - r.top;
    const laneY = 26;
    for (let i = 0; i < state.speeds.length; i++) {
      const del = speedDeleteSpot(g, i, laneY);
      if (!del) continue;
      if (Math.hypot(x - del.x, y - del.y) <= SPEED_DEL_R + 2) {
        deleteSpeedRegion(i);
        return;
      }
    }
  }
  // Trim handles only respond in 裁切 mode: a stray drag on the timeline used to
  // move a kept range after the mode was switched off.
  if (state.trimMode) {
    const edges = trimEdges(g);
    for (let i = 0; i < edges.length; i++) {
      if (Math.abs(x - edges[i].a) <= TRIM_HIT) {
        pushUndo();
        tlDrag = { kind: 'edge', i, which: 'a' };
        return;
      }
      if (Math.abs(x - edges[i].b) <= TRIM_HIT) {
        pushUndo();
        tlDrag = { kind: 'edge', i, which: 'b' };
        return;
      }
    }
  }
  if (state.speedMode) {
    // grab the region under the pointer to select it, otherwise start a new one
    const se = speedEdges(g);
    for (let i = 0; i < se.length; i++) {
      if (x >= se[i].a - 4 && x <= se[i].b + 4) {
        state.speedSel = i;
        pushUndo();
        tlDrag = { kind: 'speedEdge', i, which: x - se[i].a < se[i].b - x ? 'a' : 'b' };
        tlDragAnchor = xToTime(g, x);
        syncSpeedControls();
        drawTimeline();
        return;
      }
    }
    pushUndo();
    const t = snapTime(xToTime(g, x));
    state.speeds.push({ a: t, b: t, speed: 2 });
    state.speedSel = state.speeds.length - 1;
    tlDrag = { kind: 'speedNew', i: state.speeds.length - 1 };
    tlDragAnchor = t;
    drawTimeline();
    return;
  }
  if (state.trimMode) {
    pushUndo();
    const t = snapTime(xToTime(g, x));
    state.trims.push({ a: t, b: t });
    tlDrag = { kind: 'new', i: state.trims.length - 1 };
    tlDragAnchor = t;
    drawTimeline();
    return;
  }
  // clicking a speed region selects it, so its factor can be changed without
  // entering 变速 mode
  {
    const se = speedEdges(g);
    for (let i = 0; i < se.length; i++) {
      if (x >= se[i].a && x <= se[i].b) {
        state.speedSel = i;
        syncSpeedControls();
        drawTimeline();
        break;
      }
    }
  }
  tlDrag = { kind: 'seek' };
  seekTo(x);
});

// wheel zooms around the pointer, which is the only place you want to keep still
tlCanvas.addEventListener('wheel', (ev) => {
  if (!state.clip) return;
  ev.preventDefault();
  const r = tlCanvas.getBoundingClientRect();
  const g = tlGeom();
  const x = ev.clientX - r.left;
  const under = xToTime(g, x);
  const frac = (under - g.start) / Math.max(g.span, 1e-6);
  state.zoom = Math.max(-4, Math.min(7, (state.zoom || 0) + (ev.deltaY < 0 ? 0.5 : -0.5)));
  const span2 = Math.max(0.35, g.dur / Math.pow(2, state.zoom));
  state.tlPan = Math.max(0, Math.min(under - frac * span2, Math.max(0, g.dur - span2)));
  drawTimeline();
  drawLeft();
}, { passive: false });

tlCanvas.addEventListener('dblclick', (ev) => {
  const r = tlCanvas.getBoundingClientRect();
  const t = xToTime(tlGeom(), ev.clientX - r.left);
  // in 变速 mode a double-click removes the speed region under the pointer
  if (state.speedMode) {
    const vi = state.speeds.findIndex((x) => t >= x.a && t <= x.b);
    if (vi < 0) return;
    pushUndo();
    state.speeds.splice(vi, 1);
    state.speedSel = -1;
    normalizeSpeeds();
    syncSpeedControls();
    drawTimeline();
    drawLeft();
    markTrimDirty();
    return;
  }
  // Removing a kept range is an edit to the trim, so it too belongs to 裁切 mode.
  if (!state.trimMode) return;
  const i = state.trims.findIndex((x) => t >= x.a && t <= x.b);
  if (i < 0) return;
  pushUndo();
  state.trims.splice(i, 1);
  normalizeTrims();
  drawTimeline();
  drawLeft();
  markTrimDirty();
});

window.addEventListener('mousemove', (ev) => {
  if (!tlDrag) return;
  const r = tlCanvas.getBoundingClientRect();
  const x = ev.clientX - r.left;
  if (tlDrag.kind === 'seek') { seekTo(x); return; }
  if (tlDrag.kind === 'pan') {
    const g = tlGeom();
    const perPx = g.span / Math.max(1, g.x1 - g.x0);
    const start = panStart - (x - panAnchorX) * perPx;
    state.tlPan = Math.max(0, Math.min(start, Math.max(0, g.dur - g.span)));
    drawTimeline();
    return;
  }

  const g = tlGeom();
  const t = xToTime(g, x);
  const fps = state.bake ? state.bake.fps : 30;
  const minGap = 3 / fps;

  if (tlDrag.kind === 'new') {
    const range = state.trims[tlDrag.i];
    if (!range) return;
    const ta = snapTime(tlDragAnchor);
    const tb = snapTime(t);
    range.a = Math.min(ta, tb);
    range.b = Math.max(ta, tb);
    state.dragHint = { t: tb };
    seekToTime(tb, { noStill: true });
    drawTimeline();
    drawLeft();
    return;
  }

  if (tlDrag.kind === 'speedNew' || tlDrag.kind === 'speedEdge') {
    const region = state.speeds[tlDrag.i];
    if (!region) return;
    const snapped = snapTime(t);
    if (tlDrag.kind === 'speedNew') {
      const ta = snapTime(tlDragAnchor);
      region.a = Math.min(ta, snapped);
      region.b = Math.max(ta, snapped);
    } else if (tlDrag.which === 'a') {
      region.a = Math.min(Math.max(0, snapped), region.b - minGap);
    } else {
      region.b = Math.max(Math.min(g.dur, snapped), region.a + minGap);
    }
    state.dragHint = { t: snapped };
    drawTimeline();
    drawLeft();
    return;
  }

  const range = state.trims[tlDrag.i];
  if (!range) return;
  const snapped = snapTime(t);
  if (tlDrag.which === 'a') {
    range.a = Math.min(Math.max(0, snapped), range.b - minGap);
  } else {
    range.b = Math.max(Math.min(g.dur, snapped), range.a + minGap);
  }
  // the frame under the handle is the one being chosen, so show it
  state.dragHint = { t: tlDrag.which === 'a' ? range.a : range.b };
  seekToTime(state.dragHint.t, { noStill: true });
  drawTimeline();
  drawLeft();
});

window.addEventListener('mouseup', () => {
  if (tlDrag && tlDrag.kind === 'new') {
    // a click without a drag should not leave a zero-length range behind
    const fps = state.bake ? state.bake.fps : 30;
    const range = state.trims[tlDrag.i];
    if (range && range.b - range.a < 3 / fps) state.trims.splice(tlDrag.i, 1);
    normalizeTrims();
    drawTimeline();
    drawLeft();
    markTrimDirty();
  } else if (tlDrag && tlDrag.kind === 'edge') {
    normalizeTrims();
    drawTimeline();
    drawLeft();
    markTrimDirty();
  } else if (tlDrag && tlDrag.kind === 'speedNew') {
    const fps = state.bake ? state.bake.fps : 30;
    const region = state.speeds[tlDrag.i];
    if (region && region.b - region.a < 3 / fps) state.speeds.splice(tlDrag.i, 1);
    normalizeSpeeds();
    syncSpeedControls();
    drawTimeline();
    drawLeft();
    markTrimDirty();
  } else if (tlDrag && tlDrag.kind === 'speedEdge') {
    normalizeSpeeds();
    syncSpeedControls();
    drawTimeline();
    drawLeft();
    markTrimDirty();
  }
  if (state.dragHint) {
    state.dragHint = null;
    drawTimeline();
  }
  tlDrag = null;
});

let trimTimer = 0;
function markTrimDirty() {
  scheduleSaveEdit();
  // Trims AND speed regions change what the baked proxy should show, so it has
  // to be rebuilt; otherwise the right viewport keeps playing the old timeline.
  state.proxyStale = true;
  const pb = $('btnProxy');
  if (pb) pb.classList.add('is-on');
  clearTimeout(trimTimer);
  trimTimer = setTimeout(() => {
    const dur = state.clip ? state.clip.duration : 0;
    const full = state.trims.length === 1
      && state.trims[0].a <= 0.001
      && state.trims[0].b >= dur - 0.02;
    if (full) {
      state.trims = [];   // the whole clip kept == no trim
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
// The playhead and the timeline are both on the SOURCE clock: `state.frame` is a
// source frame and the ruler shows source seconds. Speed regions change how fast
// we walk that clock, not where the playhead sits. So playback advances a virtual
// output clock and maps it back onto source time every tick.
let playTimer = 0;
let playOutT = 0;
let playOutStart = 0;
let playOutAtStart = 0;

// The `speed` of the piece an output second falls in, 1 outside every region.
function pieceAt(outT) {
  const p = timelinePieces();
  if (!p.length) return null;
  for (const q of p) {
    if (outT < q.o + (q.b - q.a) / q.speed) return q;
  }
  return p[p.length - 1];
}

function playVideos(on) {
  const v = $('viewVideo');
  const c = $('cropVideo');
  const fps = state.bake ? state.bake.fps : 30;
  if (on) {
    // Where in the output timeline the playhead currently is.
    playOutAtStart = srcToOut(state.frame / fps);
    playOutT = playOutAtStart;
    playOutStart = performance.now();
    const piece = pieceAt(playOutT);
    const at = piece ? piece.a + Math.max(0, playOutT - piece.o) * piece.speed : playOutT;
    if (playingWithProxy()) {
      // The proxy has trims and speeds baked in: it is a timeline in its own
      // right, so it plays straight through from output second 0.
      try { c.currentTime = playOutT; c.play().catch(() => {}); } catch {}
      try { v.currentTime = at; } catch {}
    } else {
      // No proxy: the master is the moving picture, so it plays at the region's
      // rate. tickVideo re-syncs it whenever the rate changes.
      try {
        v.currentTime = at;
        v.playbackRate = Math.min(4, Math.max(0.25, piece ? piece.speed : 1));
        v.play().catch(() => {});
      } catch {}
    }
  } else {
    for (const el of [v, c]) {
      try { el.pause(); } catch {}
    }
    try { v.playbackRate = 1; } catch {}
  }
}

function tickVideo() {
  if (!state.playing) return;
  const fps = state.bake ? state.bake.fps : 30;
  const last = (state.bake ? state.bake.frames : 1) - 1;
  const v = $('viewVideo');
  const c = $('cropVideo');

  // Advance the output clock. With a proxy the element is authoritative (it is
  // the baked timeline); otherwise wall time drives it and the master follows.
  if (playingWithProxy() && c.readyState >= 2) {
    playOutT = c.currentTime;
  } else {
    playOutT = playOutAtStart + (performance.now() - playOutStart) / 1000;
  }

  const piece = pieceAt(playOutT);
  const srcT = piece ? piece.a + Math.max(0, playOutT - piece.o) * piece.speed : playOutT;
  state.frame = Math.max(0, Math.min(last, Math.round(srcT * fps)));

  if (!playingWithProxy() && state.useVideo && v.readyState >= 2) {
    // keep the picture on the playhead and on the right rate, so a region
    // boundary mid-play does not stutter or play at the old speed
    const want = piece ? piece.speed : 1;
    if (Math.abs(v.playbackRate - want) > 1e-3) {
      try { v.playbackRate = Math.min(4, Math.max(0.25, want)); } catch {}
    }
    if (Math.abs(v.currentTime - srcT) > 0.20) {
      try { v.currentTime = srcT; } catch {}
    }
  } else if (playingWithProxy() && state.useVideo && v.readyState >= 2 &&
             Math.abs(v.currentTime - srcT) > 0.25) {
    try { v.currentTime = srcT; } catch {}
  }

  drawTimeline();
  drawLeft();
  if (!playingWithProxy()) drawRight();

  const end = speedDuration();
  if (end > 0 && playOutT >= end - 1e-3) {
    if (state.loop) {
      replayFromStart();
    } else {
      stopPlayback();
    }
    return;
  }
  requestAnimationFrame(tickVideo);
}

function stopPlayback() {
  state.playing = false;
  $('icoPlay').style.display = '';
  $('icoPause').style.display = 'none';
  clearInterval(playTimer);
  playVideos(false);
  // Leave the preview parked on the frame under the playhead, so resuming or
  // scrubbing does not jump back to wherever the master happened to stop.
  const fps = state.bake ? state.bake.fps : 30;
  if (state.useVideo) seekVideos(state.frame / fps);
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
  // fallback: no video available, drive stills on a timer - on the output clock,
  // so speed regions still change the pace of the preview
  const fps = state.bake ? state.bake.fps : 30;
  const last = (state.bake ? state.bake.frames : 1) - 1;
  playTimer = setInterval(() => {
    playOutT = playOutAtStart + (performance.now() - playOutStart) / 1000;
    const piece = pieceAt(playOutT);
    const srcT = piece ? piece.a + Math.max(0, playOutT - piece.o) * piece.speed : playOutT;
    const end = speedDuration() || (state.clip ? state.clip.duration : 0);
    if (playOutT >= end - 1e-3) {
      state.frame = last;
      drawTimeline();
      drawLeft();
      scheduleStill();
      onPlaybackEnd();
      return;
    }
    state.frame = Math.max(0, Math.min(last, Math.round(srcT * fps)));
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
  const src0 = outToSrc(0);
  state.frame = Math.round(src0 * (state.bake ? state.bake.fps : 30));
  playOutAtStart = 0;
  playOutT = 0;
  playOutStart = performance.now();
  for (const el of [$('viewVideo'), $('cropVideo')]) {
    if (!el.classList.contains('is-on')) continue;
    try {
      el.currentTime = el === $('cropVideo') ? 0 : src0;
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

function togglePlay() {
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
}

$('btnPlay').onclick = togglePlay;

// Space toggles playback, the way every other editor does it. Typing fields keep
// their spaces: the inline number editor and the search box are inputs, and the
// record tab has its own shortcuts.
document.addEventListener('keydown', (e) => {
  if (e.code !== 'Space' && e.key !== ' ') return;
  if (e.repeat) return;
  const t = e.target;
  const tag = t && t.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable)) {
    return;
  }
  const rec = document.getElementById('stageRecord');
  if (rec && !rec.classList.contains('is-hidden')) return;
  e.preventDefault(); // a focused button must not also click itself
  togglePlay();
});

// Frame stepping and undo, the two things a timeline is unusable without.
document.addEventListener('keydown', (e) => {
  const t = e.target;
  const tag = t && t.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable)) return;
  const rec = document.getElementById('stageRecord');
  if (rec && !rec.classList.contains('is-hidden')) return;

  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key.toLowerCase() === 'z') {
    e.preventDefault();
    if (e.shiftKey) redo();
    else undo();
    return;
  }
  if (mod && e.key.toLowerCase() === 'y') {
    e.preventDefault();
    redo();
    return;
  }

  const fps = state.bake ? state.bake.fps : 30;
  const last = (state.bake ? state.bake.frames : 1) - 1;
  const jump = (n) => {
    state.frame = Math.max(0, Math.min(last, n));
    if (state.useVideo && !state.playing) seekVideos(state.frame / fps);
    drawTimeline();
    drawLeft();
    scheduleStill();
  };

  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    e.preventDefault();
    const step = (e.shiftKey ? 10 : 1) * (e.key === 'ArrowLeft' ? -1 : 1);
    jump(state.frame + step);
  } else if (e.key === 'Home') {
    e.preventDefault();
    jump(0);
  } else if (e.key === 'End') {
    e.preventDefault();
    jump(last);
  }
});

// ---------- editable time codes ----------
// Both the playhead readout and the trim points take typed values: dragging is
// for finding a moment, typing is for landing on an exact frame.
function editTimeInline(el, seconds, commit) {
  if (el.dataset.editing) return;
  el.dataset.editing = '1';
  const prev = el.textContent;
  const ed = document.createElement('input');
  ed.type = 'text';
  ed.className = 'row-val-edit';
  ed.value = secToTc(seconds);
  el.textContent = '';
  el.appendChild(ed);
  ed.focus();
  ed.select();
  let done = false;
  const finish = (ok) => {
    if (done) return;
    done = true;
    el.dataset.editing = '';
    const v = parseTc(ed.value);
    // setting textContent already drops the input; removing it again throws and
    // would skip the commit entirely
    el.textContent = prev;
    if (ok && v !== null) commit(v);
  };
  ed.onkeydown = (ev) => {
    if (ev.key === 'Enter') finish(true);
    else if (ev.key === 'Escape') finish(false);
    ev.stopPropagation();
  };
  ed.onblur = () => finish(true);
}

// accepts 12.5, 00:12.5, 1:02.35 or 01:02:03.4
function parseTc(text) {
  const t = (text || '').trim();
  if (!t) return null;
  const parts = t.split(':').map((x) => x.trim());
  if (parts.some((x) => x === '' || isNaN(Number(x)))) return null;
  const nums = parts.map(Number);
  if (nums.length === 1) return nums[0];
  if (nums.length === 2) return nums[0] * 60 + nums[1];
  if (nums.length === 3) return nums[0] * 3600 + nums[1] * 60 + nums[2];
  return null;
}

function secToTc(sec) {
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`;
}

$('tcNow').ondblclick = () => {
  const fps = state.bake ? state.bake.fps : 30;
  editTimeInline($('tcNow'), state.frame / fps, (v) => seekToTime(v));
};

for (const [id, which] of [['trimIn', 'a'], ['trimOut', 'b']]) {
  $(id).ondblclick = () => {
    const first = state.trims[0];
    if (!first) {
      toast('先框选一段要保留的区间');
      return;
    }
    editTimeInline($(id), first[which], (v) => {
      pushUndo();
      const fps = state.bake ? state.bake.fps : 30;
      const dur = state.clip ? state.clip.duration : v;
      const target = state.trims[0];
      if (!target) return;
      if (which === 'a') target.a = Math.max(0, Math.min(v, target.b - 3 / fps));
      else target.b = Math.min(dur, Math.max(v, target.a + 3 / fps));
      normalizeTrims();
      drawTimeline();
      drawLeft();
      markTrimDirty();
      const after = state.trims[0] || target;
      seekToTime(which === 'a' ? after.a : after.b);
    });
  };
}

$('btnProxy').onclick = generateProxy;

$('emptyGoRecord').onclick = () => {
  document.querySelector('.tab[data-tab="record"]').click();
};

$('recBadge').onclick = () => {
  document.querySelector('.tab[data-tab="record"]').click();
};

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
    ? `${m.label} · ${state.recFps} fps · 同时生成原片 / 跟拍 / 轨迹`
    : `主显示器 · ${state.recFps} fps · 同时生成原片 / 跟拍 / 轨迹`) + hk;
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
  $('recState').textContent = state.recording ? '录制中' : '待机';
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
