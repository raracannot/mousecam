import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
ov = [l for l in lines if "overlay at" in l]
err = [l for l in lines if "ERROR" in l or "STALL" in l]
print("overlay paints:", len(ov))
print("last overlay :", ov[-1][24:] if ov else "-")
print("errors/stalls:", len(err))
for l in err[:4]: print("   ", l[24:])
