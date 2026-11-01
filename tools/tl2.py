import io, os
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\test-run.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("lines:", len(lines))
bad = [l for l in lines if "ERROR" in l or "WARN" in l]
print("errors/warnings:", len(bad))
for l in bad[:6]: print("   ", l[24:])
