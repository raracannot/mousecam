import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("total:", len(lines))
bad = [l for l in lines if "STALL" in l or "ERROR" in l]
print("stall/error lines:", len(bad))
for l in bad[:6]:
    print("  ", l)
moves = [l for l in lines if "moved to" in l]
print("hud moves logged:", len(moves))
if moves:
    print("  first:", moves[0][-60:])
    print("  last :", moves[-1][-60:])
