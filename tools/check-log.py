import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\release\mousecam.log"
for i, line in enumerate(io.open(p, encoding="utf-8")):
    print(repr(line.rstrip("\n")))
    if i > 2:
        break
