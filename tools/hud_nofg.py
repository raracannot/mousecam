import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# 1) drop the focus gate: it hid the frame whenever the user touched the app,
#    which reads as "the overlay crashed and stopped drawing".
rep("""        let want = match rect {
            Some(r) if enabled && r.w > 8 && r.h > 8 && !unsafe { app_in_foreground(hwnd) } => {
                Some(r)
            }
            _ => None,
        };""",
"""        let want = match rect {
            Some(r) if enabled && r.w > 8 && r.h > 8 => Some(r),
            _ => None,
        };""")

# the helper is unused now
start = s.index("/// True when the foreground window belongs to this process")
end = s.index("static HUD_AWARE")
s = s[:start] + s[end:]

# 2) after being hidden the window keeps its old surface, but repainting is
#    cheap and makes "toggle off/on" instant instead of waiting for the camera.
rep("""            None => {
                if shown {
                    let _ = ShowWindow(hwnd, SW_HIDE);
                    shown = false;
                    last_geom = None;
                    last_paint_key = None;
                }
            }""",
"""            None => {
                if shown {
                    let _ = ShowWindow(hwnd, SW_HIDE);
                    shown = false;
                    // force a fresh paint when it comes back
                    last_paint_key = None;
                }
            }""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("focus gate removed, re-show forces a repaint")
