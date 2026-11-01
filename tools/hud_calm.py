import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for: %s" % (c, old[:140]))
    s = s.replace(old, new)

# hysteresis: sub-pixel jitter must not translate into a window move
rep("""                    if last_geom != Some(geom) {
                        let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE);
                        last_geom = Some(geom);""",
"""                    // Only move for a real change. During a window drag the
                    // cursor feeds the camera, so a 1px jitter would otherwise
                    // turn into an 80 Hz stream of SetWindowPos calls that fight
                    // the drag for the compositor.
                    let moved = match last_geom {
                        Some(g) => {
                            (g.0 - wx).abs() > 2
                                || (g.1 - wy).abs() > 2
                                || (g.2 - ww).abs() > 2
                                || (g.3 - wh).abs() > 2
                        }
                        None => true,
                    };
                    if moved {
                        let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE);
                        last_geom = Some(geom);
                        crate::mc_debug!(
                            "hud",
                            "moved to {},{} {}x{} (crop {}x{})",
                            wx, wy, ww, wh, r.w, r.h
                        );""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("hud hysteresis added")

# slower tick: a boundary rectangle does not need 80 Hz
s = io.open(p, encoding="utf-8").read()
import re
m = re.search(r"std::thread::sleep\(std::time::Duration::from_millis\((\d+)\)\);", s)
print("current sleep:", m.group(1) if m else "none")
if m:
    s = s[:m.start()] + "std::thread::sleep(std::time::Duration::from_millis(33));" + s[m.end():]
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("tick -> 33ms (30 Hz)")
