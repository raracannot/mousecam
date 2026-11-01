import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
lines = io.open(p, encoding="utf-8").read().split("\n")
for i, l in enumerate(lines):
    if "setCapturesHint" in l:
        print(i+1, repr(l))
