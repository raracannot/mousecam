import io
p = r"E:\RAYS\Desktop\workspace\mousecam\tools\verify-timeline.mjs"
s = io.open(p, encoding="utf-8").read()

start = s.index("  // ---------- 4) zoom actually narrows the visible window")
end = s.index("  // ---------- 5) switching clips clears trims and keyframes")
new = '''  // ---------- 4) zoom actually narrows the visible window ----------
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

'''
s = s[:start] + new + s[end:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("zoom check rewritten")
