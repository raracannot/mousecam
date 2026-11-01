import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
old = "WM_DESTROY, WM_ERASEBKGND, WM_PAINT,"
assert s.count(old) == 1, s.count(old)
s = s.replace(old, "IsWindowVisible, WM_DESTROY, WM_ERASEBKGND, WM_PAINT,")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("IsWindowVisible imported")
