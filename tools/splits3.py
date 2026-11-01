import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

# the shared helper was left unused and its null onDelta would throw on move
start = s.index("  const drag = (handle, axis, onDelta, onDone) => {")
end = s.index("  const clamp = (v, lo, hi) =>", start)
s = s[:start] + s[end:]
s = s.replace("  drag($('splitVp'), 'x', null, () => {});\n", "")

# capture can throw for a synthetic pointer id; never let that kill the drag
s = s.replace("      handle.setPointerCapture(e.pointerId);",
              "      try { handle.setPointerCapture(e.pointerId); } catch {}")
s = s.replace("      h.setPointerCapture(e.pointerId);",
              "      try { h.setPointerCapture(e.pointerId); } catch {}")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("cleaned up")
