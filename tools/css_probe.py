import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
lines = io.open(p, encoding="utf-8").read().split("\n")
for i, l in enumerate(lines):
    if ".stage {" in l or ".viewports {" in l:
        print("L%d: %r" % (i+1, l))
        for k in range(1, 5):
            print("     %r" % lines[i+k])
        print()
