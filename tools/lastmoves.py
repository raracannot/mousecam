import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
moves = [l for l in lines if "moved to" in l]
print("moves:", len(moves))
for l in moves[-4:]:
    print("  ", l)
