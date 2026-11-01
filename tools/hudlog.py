import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
for l in io.open(p, encoding="utf-8"):
    if "hud" in l.lower() or "ERROR" in l:
        print(l.rstrip())
