import io
p = r"rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for:\n%s" % (c, old[:150]))
    s = s.replace(old, new)

rep("  nvenc: null,", "  nvenc: null,\n  appSettings: null,")

# ---- settings dialog wiring (placed with the rest of the window controls)
rep("""$('wbMax').onclick = () => getWin().toggleMaximize();""",
"""$('wbMax').onclick = () => getWin().toggleMaximize();

/* ---------------- app settings ---------------- */
async function loadAppSettings() {
  try {
    const [effective, configured, hw, hud] = await invoke('app_settings');
    state.appSettings = { effective, configured, hw, hud };
  } catch {
    state.appSettings = null;
  }
  return state.appSettings;
}

function paintSettingsDialog() {
  const a = state.appSettings || {};
  $('setCaptures').value = a.configured || '';
  $('setCaptures').placeholder = a.effective || '默认位置';
  $('setCapturesHint').textContent = `当前生效：${a.effective || '（未知）'}`;
  $('setHw').checked = !!a.hw;
  $('setHud').checked = !!a.hud;
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
  try {
    await invoke('set_app_settings', { capturesDir: dir, hw, hud });
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
};""")

# boot: pull the settings before the first paint
rep("""  paintLoopToggle();
  pushHudConfig();""",
"""  paintLoopToggle();
  pushHudConfig();
  loadAppSettings().then((a) => {
    if (!a) return;
    state.hw = !!a.hw;
    $('hudToggle').classList.toggle('is-on', !!a.hud);
    invoke('hud_set', { enabled: !!a.hud }).catch(() => {});
  });""")

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("settings dialog wired")
