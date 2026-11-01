import io, re
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
n = sum(1 for l in io.open(p, encoding="utf-8") if "moved to" in l)
print("moved lines:", n)
