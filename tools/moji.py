import io, re, os
root = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui"
sus = ["鍚", "锛", "鈥", "鐨", "鏄", "鎴", "涓", "寮", "鍙", "瀹"]
for name in ("app.js", "index.html", "app.css"):
    p = os.path.join(root, name)
    s = io.open(p, encoding="utf-8", errors="replace").read()
    repl = s.count("\ufffd")
    hits = {c: s.count(c) for c in sus if s.count(c)}
    print("%-11s replacement=%d  mojibake-markers=%s" % (name, repl, dict(list(hits.items())[:6])))
