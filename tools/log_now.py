import io, os
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
if not os.path.exists(p):
    raise SystemExit("no log")
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("total lines:", len(lines))
print("last 14 lines:")
for l in lines[-14:]:
    print("  ", l)
print()
for kw in ("STALL", "heartbeat", "resumed", "ERROR", "BLACK", "grab failed"):
    hits = [l for l in lines if kw in l]
    if hits:
        print("%s: %d" % (kw, len(hits)))
        for l in hits[-3:]:
            print("    ", l[24:])
