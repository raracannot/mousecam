import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = """    $('setCapturesHint').textContent = `当前生效：${a.effective || '（未知）'}`;"""
new = """    // When the configured folder cannot be written the engine falls back to one
    // that can; saying so here is the difference between "why did my recordings
    // go somewhere else" and a message that answers it.
    const configured = (a.configured || '').trim();
    const effective = (a.effective || '').trim();
    if (effective && configured && configured !== effective) {
      $('setCapturesHint').textContent = `该文件夹不可写（常见于安全软件拦截），实际使用：${effective}`;
      $('setCapturesHint').classList.add('is-warn');
    } else {
      $('setCapturesHint').textContent = `当前生效：${effective || '（未知）'}`;
      $('setCapturesHint').classList.remove('is-warn');
    }"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("dialog explains the fallback")

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
if ".is-warn" not in s:
    s += """
/* a note that reports a real problem, not just information */
.set-hint.is-warn {
  color: #f0b45a;
}
"""
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("warning style added")
