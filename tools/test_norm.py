import io, re

NORM = """
  // Normalise the editor before measuring anything: a trim or a keyframe left
  // by another suite puts grips under the clicks and silently swallows them.
  await cdp.eval(`(() => {
    const t = document.getElementById('trimToggle');
    if (t && t.classList.contains('is-on')) t.click();
    const k = document.getElementById('kfToggle');
    if (k && k.classList.contains('is-on')) k.click();
    window.__mc.trim = null;
    window.__mc.kfs = [];
    window.__mc.frame = 0;
    window.__mc.zoom = 0;
    document.querySelectorAll('#tlZoom button')[0]?.click();
  })()`);
  await sleep(300);
"""

targets = {
    r"tools\verify.mjs": """  await cdp.eval(`document.querySelector('.tab[data-tab="edit"]').click()`);
  await sleep(600);""",
    r"tools\verify-timeline.mjs": """  await cdp.eval(`document.querySelector('.tab[data-tab="edit"]').click()`);
  await sleep(800);""",
}

for rel, anchor in targets.items():
    p = r"E:\RAYS\Desktop\workspace\mousecam" + "\\" + rel
    s = io.open(p, encoding="utf-8").read()
    if "Normalise the editor before measuring" in s:
        print("already normalised:", rel)
        continue
    c = s.count(anchor)
    if c != 1:
        print("SKIP (anchor %d):" % c, rel)
        continue
    s = s.replace(anchor, anchor + NORM)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("normalised:", rel)
