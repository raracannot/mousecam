import io, os
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
if not os.path.exists(p):
    print("no log")
else:
    lines = [l.rstrip("\n") for l in io.open(p, encoding="utf-8")]
    print("total lines:", len(lines))
    interesting = [l for l in lines if "ERROR" in l or "WARN" in l or "STALL" in l or "panic" in l]
    print("error/warn/stall lines:", len(interesting))
    for l in interesting[-25:]:
        print("  ", l)
    print("--- last 12 lines ---")
    for l in lines[-12:]:
        print("  ", l)
