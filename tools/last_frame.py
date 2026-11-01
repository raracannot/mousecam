import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\test-run.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
sends = [l for l in lines if "| frame" in l]
print("last sent:", sends[-1][24:] if sends else "none")
