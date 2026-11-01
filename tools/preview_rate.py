import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = "  if (state.recPreviewOn) recPreviewTimer = setTimeout(tickRecPreview, 110);"
new = """  // While recording the preview shares the main thread with the capture and
  // encoder plumbing; 5 fps is still enough to aim the camera and costs half.
  if (state.recPreviewOn) {
    recPreviewTimer = setTimeout(tickRecPreview, state.recording ? 200 : 110);
  }"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("preview poll relaxed while recording")
