import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\log.rs"
s = io.open(p, encoding="utf-8").read()
old = "    if s.repeats > 0 {"
new = "    if s.repeats > 1 {"
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("dedupe summary only for real repeats")
