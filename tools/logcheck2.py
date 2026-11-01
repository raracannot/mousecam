import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("total:", len(lines))
warn = [l for l in lines if "WARN" in l or "ERROR" in l]
print("warn/error lines:", len(warn))
for l in warn[:5]:
    print("  ", l)
