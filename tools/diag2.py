import io, os
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("total:", len(lines), "| last line:", lines[-1][:60] if lines else "-")
bad = [l for l in lines if "ERROR" in l or "STALL" in l or "WARN" in l]
print("error/warn/stall:", len(bad))
for l in bad[-12:]:
    print("  ", l)
import re
moves = [l for l in lines if "moved to" in l]
print("hud moves:", len(moves))
sizes = set()
for l in moves:
    m = re.search(r"moved to -?\d+,-?\d+ (\d+)x(\d+)", l)
    if m: sizes.add((int(m.group(1)), int(m.group(2))))
print("distinct window sizes:", sorted(sizes))
