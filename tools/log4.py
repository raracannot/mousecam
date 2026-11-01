import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = '''        mc_engine::mc_info!(
            "app",
            "monitor {}: {}x{} at {},{} primary={} scale~{:.2}",
            m.index, m.w, m.h, m.x, m.y, m.primary, m.scale
        );'''
new = '''        mc_engine::mc_info!(
            "app",
            "monitor {}: {}x{} at {},{} primary={}",
            m.index, m.w, m.h, m.x, m.y, m.primary
        );'''
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("monitor log fixed")
