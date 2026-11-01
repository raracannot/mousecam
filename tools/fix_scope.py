import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
lines = io.open(p, encoding="utf-8").read().split("\n")

a = next(i for i, l in enumerate(lines) if "app settings ----" in l)
b = next(i for i, l in enumerate(lines) if "$('wbClose').onclick" in l)
assert a < b
block = lines[a:b]
rest = lines[:a] + lines[b:]
print("moved %d lines of settings code" % len(block))

# drop the blank line the removal left behind
while rest[a].strip() == "" and rest[a-1].strip() == "":
    del rest[a]

c = next(i for i, l in enumerate(rest) if "$('wbClose').onclick" in l)
d = next(i for i in range(c, len(rest)) if rest[i].strip() == "} else {")
e = next(i for i in range(d + 1, len(rest)) if rest[i].strip() == "}")
print("inserting after line", e + 1, "->", rest[e])
rest[e+1:e+1] = [""] + block
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(rest))
print("settings code hoisted to module scope")
