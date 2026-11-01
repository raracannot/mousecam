import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = """      const box = $('recHw');
      box.checked = !!state.nvenc;
      state.hw = !!state.nvenc;
      box.disabled = !state.nvenc;"""
new = """      const box = $('recHw');
      // The saved preference decides this, not the probe: NVENC being available
      // does not mean the user wants it. It only has to be forced off when the
      // hardware cannot do it at all.
      const want = state.appSettings ? !!state.appSettings.hw : true;
      state.hw = !!state.nvenc && want;
      box.checked = state.hw;
      box.disabled = !state.nvenc;"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("hw preference respected")
