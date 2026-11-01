import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()
s = s.replace("crate::log::init(&log_path, true);", "crate::log::init(log_path, true);")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("fixed")
