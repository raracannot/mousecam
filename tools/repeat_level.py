import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\log.rs"
s = io.open(p, encoding="utf-8").read()
old = """            "{}  {}  [{:<10}] ... 上一行又重复了 {} 次\\n",
            stamp(),
            "WARN ","""
new = """            "{}  {}  [{:<10}] ... 上一行又重复了 {} 次\\n",
            stamp(),
            "DEBUG","""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("repeat summary no longer warns")
