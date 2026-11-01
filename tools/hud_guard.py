import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:80]))
    s = s.replace(old, new)

# a toggle that is disabled while recording cannot put the frame back into the file
rep("""$('hudToggle').onclick = async () => {""",
"""$('hudToggle').onclick = async () => {
  // turning it back on mid-recording would write the border into the file
  if (state.recording) {
    toast('录制期间取景框会自动隐藏，停止后可重新打开', 2200);
    return;
  }""")
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("guard added")

# dim the button while recording so the rule is visible, not just enforced
i = s.index("function setRecording(")
j = s.index("\n}", i)
body = s[i:j]
if "hudToggle" not in body:
    s = s[:j] + "\n  const ht = $('hudToggle');\n  if (ht) {\n    ht.classList.toggle('is-disabled', on);\n    ht.title = on ? '录制期间取景框自动隐藏' : '在屏幕上显示跟拍取景框（不会被录进去）';\n  }" + s[j:]
    io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
    print("button dimmed while recording")
