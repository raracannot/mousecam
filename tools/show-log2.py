import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip("\n") for l in io.open(p, encoding="utf-8")]
print("\n".join(lines[:22]))
print("...")
print("total lines:", len(lines))
