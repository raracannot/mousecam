import io, re

# ---------- 1. markup: three drag handles ----------
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\index.html"
s = io.open(p, encoding="utf-8").read()

# between the two viewports
m = re.search(r'(</article>)\s*(<article class="vp">)', s)
assert m, "viewport pair not found"
s = s[:m.end(1)] + '\n\n      <div class="split split-v" id="splitVp" title="拖动调整两栏宽度"></div>\n\n      ' + s[m.start(2):]

# between the viewport row and the timeline
m = re.search(r'(</section>)\s*(<!--[^>]*timeline)', s, re.S)
assert m, "viewports/timeline boundary not found"
s = s[:m.end(1)] + '\n\n    <div class="split split-h" id="splitStageA" title="拖动调整取景区高度"></div>\n\n    ' + s[m.start(2):]

# between the timeline and the params
m = re.search(r'(</section>)\s*(<section class="params")', s, re.S)
assert m, "timeline/params boundary not found"
s = s[:m.end(1)] + '\n\n    <div class="split split-h" id="splitStageB" title="拖动调整参数区高度"></div>\n\n    ' + s[m.start(2):]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("handles inserted")

# ---------- 2. layout ----------
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
s = s.replace("""  .stage {
    display: grid;
    grid-template-rows: minmax(0, 1fr) 104px 176px;""",
"""  .stage {
    display: grid;
    /* viewports take the rest, the timeline and the params are draggable */
    grid-template-rows: minmax(120px, 1fr) 8px var(--tl-h, 104px) 8px var(--params-h, 176px);""")
s = s.replace("""  .viewports {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--sp-3);""",
"""  .viewports {
    display: grid;
    grid-template-columns: var(--vp-left, 1fr) 14px minmax(0, 1fr);
    gap: 0;""")
s += """
/* ============================================================
   Split handles
   ============================================================ */
.split {
  position: relative;
  z-index: 5;
  touch-action: none;
}
.split::after {
  content: '';
  position: absolute;
  background: var(--line);
  border-radius: 2px;
  transition: background .12s ease;
}
.split-v { cursor: col-resize; }
.split-v::after { left: 6px; top: 12%; width: 2px; height: 76%; }
.split-h { cursor: row-resize; }
.split-h::after { top: 3px; left: 12%; height: 2px; width: 76%; }
.split:hover::after,
.split.dragging::after { background: var(--accent); }
body.split-drag { user-select: none; }
body.split-drag.cols { cursor: col-resize; }
body.split-drag.rows { cursor: row-resize; }
body.split-drag * { pointer-events: none; }
"""
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("layout and handle styling updated")
