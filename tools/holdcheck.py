import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
hold = [l for l in lines if "holding still" in l]
print("holding-still lines:", len(hold))
for l in hold[-2:]:
    print("  ", l)
