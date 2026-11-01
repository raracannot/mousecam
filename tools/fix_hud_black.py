import io
p = r"rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for:\n%s" % (c, old[:150]))
    s = s.replace(old, new)

# 1) the window must erase to the colour KEY, never to black. Without a class
#    brush any newly exposed area (the window grows as the camera zooms) showed
#    up as an opaque black rectangle until the next manual repaint.
rep("""    let hinst = GetModuleHandleW(None).unwrap_or_default();
    let class = WNDCLASSW {
        style: CS_HREDRAW | CS_VREDRAW,
        lpfnWndProc: Some(wndproc),
        hInstance: hinst.into(),
        lpszClassName: w!("MouseCamHud"),
        ..Default::default()
    };""",
"""    let hinst = GetModuleHandleW(None).unwrap_or_default();
    let key_brush = windows::Win32::Graphics::Gdi::CreateSolidBrush(KEY);
    let class = WNDCLASSW {
        style: CS_HREDRAW | CS_VREDRAW,
        lpfnWndProc: Some(wndproc),
        hInstance: hinst.into(),
        // erase to the colour key so an exposed strip is transparent, never a
        // black bar (this window has no message pump, so WM_PAINT only runs
        // when we call paint ourselves)
        hbrBackground: windows::Win32::Graphics::Gdi::HBRUSH(key_brush.0),
        lpszClassName: w!("MouseCamHud"),
        ..Default::default()
    };""")

# 2) repaint whenever the geometry changes, not just when the config does
rep("""                let key = (
                    ww,
                    wh,
                    cfg.thickness,
                    cfg.show_label,
                    cfg.brackets,
                    label.len(),
                );""",
"""                let key = (
                    ww,
                    wh,
                    cfg.thickness,
                    cfg.show_label,
                    cfg.brackets,
                    label.len(),
                );
                let _ = &key;""")

rep("""                if last_paint_key != Some(key) {""",
"""                // A resize exposes fresh pixels, so geometry belongs in the
                // repaint key as much as the appearance does.
                if last_paint_key != Some(key) || resized {""")

rep("""                if last_geom != Some(geom) {
                    let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE);
                    last_geom = Some(geom);
                }""",
"""                let resized = last_geom.map(|g| (g.2, g.3) != (ww, wh)).unwrap_or(true);
                if last_geom != Some(geom) {
                    let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE);
                    last_geom = Some(geom);
                }""")

# 3) we paint everything ourselves; tell Windows not to erase over it
rep("""            WM_DESTROY => LRESULT(0),""",
"""            WM_ERASEBKGND => LRESULT(1),
            WM_DESTROY => LRESULT(0),""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("hud black-block fix applied")
