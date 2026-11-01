import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\test-run.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
for l in lines:
    if "hud" in l or "ERROR" in l:
        print("  ", l[24:])
