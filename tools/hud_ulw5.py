import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
old = 'crate::mc_debug!("hud", "{},{}" + " {}x{} (crop {}x{})", wx, wy, ww, wh, r.w, r.h);'
new = 'crate::mc_debug!("hud", "overlay at {},{} {}x{} (crop {}x{})", wx, wy, ww, wh, r.w, r.h);'
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("log fixed")
