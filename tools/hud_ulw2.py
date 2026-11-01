import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:100]))
    s = s.replace(old, new)

# creation: no colour key, no class brush - ULW supplies the pixels
rep("""    let key_brush = windows::Win32::Graphics::Gdi::CreateSolidBrush(KEY);
    let class = WNDCLASSW {""", """    let class = WNDCLASSW {""")
rep("""        hbrBackground: windows::Win32::Graphics::Gdi::HBRUSH(key_brush.0),
""", "")
rep("""    let _ = SetLayeredWindowAttributes(hwnd, KEY, 255, LWA_COLORKEY);
""", """    // No SetLayeredWindowAttributes: the surface comes from UpdateLayeredWindow.
""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("creation updated")

# the loop: keep a surface and paint with the window geometry
lines = io.open(p, encoding="utf-8").read().split("\n")
i = next(i for i, l in enumerate(lines) if "let mut last_geom" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines[i:i] = [
    ind + "let mut surf: Option<Surface> = None;",
]
src = "\n".join(lines)
src = src.replace(
"""                let key = (ww, wh, cfg.thickness, cfg.show_label, cfg.brackets, label.clone());
                if last_paint_key.as_ref() != Some(&key) {
                    paint(hwnd, &label, cfg, Some((pad, pad, r.w, r.h)));
                    last_paint_key = Some(key);
                }""",
"""                let key = (ww, wh, cfg.thickness, cfg.show_label, cfg.brackets, label.clone());
                let stale = surf.as_ref().map(|s| (s.w, s.h) != (ww, wh)).unwrap_or(true);
                if stale {
                    surf = Surface::new(ww, wh);
                }
                if let Some(s) = surf.as_mut() {
                    if last_paint_key.as_ref() != Some(&key) || last_geom != Some(geom) {
                        if paint(hwnd, s, wx, wy, &label, cfg, Some((pad, pad, r.w, r.h))) {
                            last_paint_key = Some(key);
                        }
                    }
                }""")
io.open(p, "w", encoding="utf-8", newline="").write(src)
print("loop wired to the surface")
