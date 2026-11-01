import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\test-run.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
sends = [l for l in lines if "send cfg" in l]
print("frames sent:", len(sends))
for l in sends[-6:]:
    print("  ", l[24:])
print()
prev = [l for l in lines if "preview" in l and "crop" in l]
print("preview lines:", len(prev))
for l in prev[-4:]:
    print("  ", l[24:])
