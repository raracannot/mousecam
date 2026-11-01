import io

# js defaults
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()
old = """  edit: {
    zoom: 1.0,
    expand: 1.5,
    threshold: 1500,
    smooth: 55,
    resp: 35,
    follow: 2.2,
    look: 60,
    aspect: 0,
    width: 1280,
  },"""
new = """  edit: {
    zoom: 1.0,
    expand: 1.2,
    threshold: 3400,
    smooth: 66,
    resp: 35,
    follow: 1.0,
    look: 60,
    aspect: 0,
    width: 1080,
  },"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("js defaults updated")

# engine defaults, so new recordings bake with the same numbers
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\settings.rs"
s = io.open(p, encoding="utf-8").read()
old = """            fps: 30,
            out_width: 1280,
            aspect_idx: 0,
            zoom: 1.0,
            speed_expand: 1.5,
            speed_threshold: 1500.0,
            smooth: 55.0,
            speed_resp: 35.0,
            follow_hz: 2.2,"""
new = """            fps: 30,
            out_width: 1080,
            aspect_idx: 0,
            zoom: 1.0,
            speed_expand: 1.2,
            speed_threshold: 3400.0,
            smooth: 66.0,
            speed_resp: 35.0,
            follow_hz: 1.0,"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("engine defaults updated")
