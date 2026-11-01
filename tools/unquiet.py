import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = "const QUIET_CALLS = new Set(['preview_frame', 'record_status', 'hud_get', 'hud_get_config', 'media_path', 'still', 'heartbeat']);"
new = """// preview_frame used to be silenced because it fails at 8 Hz while the engine
// warms up; the Rust logger collapses identical consecutive lines, so it is safe
// to surface now - and a preview that stops producing frames must not be silent.
const QUIET_CALLS = new Set(['record_status', 'hud_get', 'hud_get_config', 'media_path', 'still', 'heartbeat']);"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("preview_frame failures surface again")
