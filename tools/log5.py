import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != 1:
        raise SystemExit("matched %d for: %s" % (c, old[:140]))
    s = s.replace(old, new)

# 1) ship every frontend failure to the log file, and trace failed calls
rep("""const invoke = IS_TAURI ? T.core.invoke : httpInvoke;""",
"""// Frontend failures are invisible unless someone has DevTools open, so they go
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

function traced(fn) {
  return async (cmd, args) => {
    try {
      return await fn(cmd, args);
    } catch (e) {
      logUi('error', `调用 ${cmd} 失败: ${e}`);
      throw e;
    }
  };
}

const invoke = traced(IS_TAURI ? T.core.invoke.bind(T.core) : httpInvoke);""")

# 2) the settings tuple gained `verbose`
rep("""    const [effective, configured, hw, hud] = await invoke('app_settings');
    state.appSettings = { effective, configured, hw, hud };""",
"""    const [effective, configured, hw, hud, verbose] = await invoke('app_settings');
    state.appSettings = { effective, configured, hw, hud, verbose };""")

rep("""  $('setHw').checked = !!a.hw;
  $('setHud').checked = !!a.hud;""",
"""  $('setHw').checked = !!a.hw;
  $('setHud').checked = !!a.hud;
  if ($('setVerbose')) $('setVerbose').checked = !!a.verbose;""")

rep("""  const hw = $('setHw').checked;
  const hud = $('setHud').checked;
  try {
    await invoke('set_app_settings', { capturesDir: dir, hw, hud });""",
"""  const hw = $('setHw').checked;
  const hud = $('setHud').checked;
  const verbose = $('setVerbose') ? $('setVerbose').checked : false;
  try {
    await invoke('set_app_settings', { capturesDir: dir, hw, hud, verbose });""")

# 3) a button that opens the log, next to the folder buttons
rep("""$('setOpen').onclick = async () => {""",
"""if ($('setOpenLog')) {
  $('setOpenLog').onclick = async () => {
    try {
      await invoke('open_log');
    } catch (e) {
      toast('无法打开日志: ' + e, 3000);
    }
  };
}

$('setOpen').onclick = async () => {""")

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("app.js wired")
