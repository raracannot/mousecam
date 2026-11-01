import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip("\n") for l in io.open(p, encoding="utf-8")]
moves = [l for l in lines if "moved to" in l]
hold = [l for l in lines if "holding still" in l]
print("total lines:", len(lines), "| moved:", len(moves), "| holding-still:", len(hold))
for l in lines[-8:]:
    print("  ", l)
