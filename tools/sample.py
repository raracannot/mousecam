import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
lines = [l.rstrip() for l in io.open(p, encoding="utf-8")]
print("sample of what to look for:")
for l in lines:
    if "watch" in l or "preview" in l:
        print("   ", l[24:])
