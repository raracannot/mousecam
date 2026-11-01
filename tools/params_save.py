import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:90]))
    s = s.replace(old, new)

# 1) storage helpers next to the defaults
rep("const DEFAULTS = { ...state.edit };",
"""const DEFAULTS = { ...state.edit };

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
}""")

# 2) restore the frame settings too
rep("const hudCfg = { thickness: 2, label: true, brackets: true };",
"""const hudCfg = {
  thickness: 2,
  label: true,
  brackets: true,
  ...(SAVED_PARAMS.hud && typeof SAVED_PARAMS.hud === 'object' ? SAVED_PARAMS.hud : {}),
};""")

# 3) persist on every change
rep("""function pushHudConfig() {
  if (!IS_TAURI) return;""",
"""function pushHudConfig() {
  saveParams();
  if (!IS_TAURI) return;""")

rep("""function onParamChanged() {
  clearTimeout(rebakeTimer);""",
"""function onParamChanged() {
  saveParams();
  clearTimeout(rebakeTimer);""")
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("persistence wired")
