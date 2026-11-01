import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

old = """async function loadAppSettings() {
  try {
    const [effective, configured, hw, hud, verbose] = await invoke('app_settings');
    state.appSettings = { effective, configured, hw, hud, verbose };
  } catch {
    state.appSettings = null;
  }
  return state.appSettings;
}"""
new = """async function loadAppSettings() {
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
}"""
assert s.count(old) == 1
s = s.replace(old, new)

old2 = """  loadAppSettings().then((a) => {
    if (!a) return;"""
new2 = """  loadAppSettings().then((a) => {
    if (!a) {
      // one retry: the very first call can land before the IPC bridge is ready
      setTimeout(() => loadAppSettings(), 700);
      return;
    }"""
assert s.count(old2) == 1
s = s.replace(old2, new2)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("settings load logs failures and retries once")
