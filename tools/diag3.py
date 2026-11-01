import io, re
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("total:", len(lines))
for kw in ("heartbeat", "frames published", "grab failed", "STALL", "ERROR"):
    hits = [l for l in lines if kw in l]
    print("%-16s %d" % (kw + ":", len(hits)))
    for l in hits[:2]:
        print("    ", l[24:])
moves = [l for l in lines if "moved to" in l]
sizes = set()
for l in moves:
    m = re.search(r"moved to -?\d+,-?\d+ (\d+)x(\d+)", l)
    if m: sizes.add((int(m.group(1)), int(m.group(2))))
print("hud moves:", len(moves), "| distinct sizes:", sorted(sizes))
