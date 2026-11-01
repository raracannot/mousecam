import io
p = r"E:\RAYS\Desktop\workspace\mousecam\tools\drag_win.ps1"
s = io.open(p, encoding="utf-8").read()
s = s.replace("$startX = $r.l + [int](($r.r - $r.l) / 2)", "$startX = $r.l + 40")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("grab point moved to the brand area")
