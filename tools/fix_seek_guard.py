import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = """  // The master video has to follow the playhead even without a proxy, otherwise
  // clicking the timeline only moves the trace and the right pane.
  if (state.useVideo) seekVideos(state.frame / fps);"""
new = """  // The master video has to follow the playhead even without a proxy, otherwise
  // clicking the timeline only moves the trace and the right pane. Never seek
  // while playing: the video IS the clock then, and seeking from state.frame
  // would drag it back every time this runs.
  if (state.useVideo && !state.playing) seekVideos(state.frame / fps);"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("seek guarded against playback")
