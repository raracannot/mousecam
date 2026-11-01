import io, time
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\target\debug\mousecam.log"
n0 = sum(1 for _ in io.open(p, encoding="utf-8"))
time.sleep(5)
n1 = sum(1 for _ in io.open(p, encoding="utf-8"))
print("log lines added in 5s while the preview runs:", n1 - n0)
