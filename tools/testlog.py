import io, os
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\test-run.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("lines:", len(lines))
for l in lines:
    if "capture" in l or "ERROR" in l or "STALL" in l:
        print("  ", l[24:])
