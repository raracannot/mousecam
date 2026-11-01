import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
for l in lines:
    if "preview" in l or "watch" in l:
        print("   ", l[24:])
