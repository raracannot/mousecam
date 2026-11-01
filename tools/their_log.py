import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("total:", len(lines))
print("--- first 3 ---")
for l in lines[:3]: print("  ", l)
print("--- last 18 ---")
for l in lines[-18:]: print("  ", l)
import collections
kinds = collections.Counter()
for l in lines:
    if "overlay at" in l: kinds["overlay"] += 1
    elif "STALL" in l: kinds["STALL"] += 1
    elif "heartbeat" in l: kinds["heartbeat"] += 1
    elif "ERROR" in l: kinds["ERROR"] += 1
    elif "frames published" in l: kinds["frames"] += 1
    elif "BLACK" in l: kinds["BLACK"] += 1
print("--- counts ---")
for k, v in kinds.items(): print("  %-10s %d" % (k, v))
