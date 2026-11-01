import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip("\n") for l in io.open(p, encoding="utf-8")]
print("total:", len(lines))
for l in lines:
    if "ERROR" in l or "WARN" in l or "holding still" in l:
        print(" ", l)
