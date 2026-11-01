import io
p = r"E:\RAYS\Desktop\workspace\mousecam\tools\verify-edit.mjs"
s = io.open(p, encoding="utf-8").read()
old = """  await cdp.eval(`(() => { const s = window.__mc; s.frame = 0;
    for (const el of [document.getElementById('viewVideo'), document.getElementById('cropVideo')]) {
      try { el.currentTime = 0; } catch {}
    } })()`);
  await sleep(250);
  await cdp.eval(`document.getElementById('btnPlay').click()`);
  await sleep(1600);
  const f1 = await cdp.eval(`window.__mc.frame`);
  const ct = await cdp.eval(`document.getElementById('viewVideo').currentTime`);
  await sleep(900);
  const f2 = await cdp.eval(`window.__mc.frame`);"""
new = """  // Start a quarter into the clip: a short clip would otherwise finish before the
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
  const f2 = await cdp.eval(`window.__mc.frame`);"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("playback check made duration-independent")
