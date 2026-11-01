import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
# surrogateescape so the mojibake bytes elsewhere survive untouched
raw = io.open(p, encoding="utf-8", errors="surrogateescape").read()
lines = raw.split("\n")
idx = next(i for i, l in enumerate(lines) if "setCapturesHint" in l)
indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
new = [
    indent + "// When the configured folder cannot be written the engine falls back to",
    indent + "// one that can; saying so here answers \"why did my recordings go elsewhere\".",
    indent + "const configured = (a.configured || '').trim();",
    indent + "const effective = (a.effective || '').trim();",
    indent + "if (effective && configured && configured !== effective) {",
    indent + "  $('setCapturesHint').textContent = `该文件夹不可写（常见于安全软件拦截），实际使用：${effective}`;",
    indent + "  $('setCapturesHint').classList.add('is-warn');",
    indent + "} else {",
    indent + "  $('setCapturesHint').textContent = `当前生效：${effective || '（未知）'}`;",
    indent + "  $('setCapturesHint').classList.remove('is-warn');",
    indent + "}",
]
lines[idx:idx+1] = new
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write("\n".join(lines))
print("hint rewritten (line %d)" % (idx + 1))
