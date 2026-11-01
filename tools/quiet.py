import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = "const QUIET_CALLS = new Set(['preview_frame', 'record_status', 'hud_get', 'hud_get_config']);"
new = ("// media_path fails for every clip that has no proxy yet, which is normal.\n"
       "const QUIET_CALLS = new Set(['preview_frame', 'record_status', 'hud_get', 'hud_get_config', 'media_path']);")
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("media_path quieted")
