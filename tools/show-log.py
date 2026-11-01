import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\release\mousecam.log"
lines = [l.rstrip("\n") for l in io.open(p, encoding="utf-8")]
for l in lines:
    if "[record" in l or "[export" in l or "[panic" in l or "ERROR" in l:
        print(l)
print("total lines:", len(lines))
