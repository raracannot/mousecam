import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# restore the per-frame window (revert the full-monitor slab)
start = next(i for i, l in enumerate(lines) if l.strip() == "Some(r) => {")
none_i = next(i for i in range(start, len(lines)) if lines[i].strip() == "None => {")
ind = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
b = ind + "    "
body = [
    ind + "Some(r) => {",
    b + "let pad = cfg.thickness.clamp(1, 8) + 2;",
    b + "let (wx, wy) = m.pt(r.x - pad, r.y - pad);",
    b + "let (ww, wh) = m.len(r.w + pad * 2, r.h + pad * 2);",
    b + "let (ww, wh) = (ww.clamp(8, 8192), wh.clamp(8, 8192));",
    b + "let geom = (wx, wy, ww, wh);",
    b + "",
    b + "// Move/resize only for a real change, at most ~14 times a second, and never",
    b + "// while the mouse button is held: that is when a window is being dragged and",
    b + "// a layered window chasing it fights the compositor.",
    b + "let moved = match last_geom {",
    b + "    Some(g) => {",
    b + "        (g.0 - wx).abs() > 2 || (g.1 - wy).abs() > 2",
    b + "            || (g.2 - ww).abs() > 2 || (g.3 - wh).abs() > 2",
    b + "    }",
    b + "    None => true,",
    b + "};",
    b + "let dragging = unsafe {",
    b + "    use windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;",
    b + "    (GetAsyncKeyState(0x01) as u16 & 0x8000) != 0",
    b + "};",
    b + "if moved && !dragging && last_move.elapsed() >= std::time::Duration::from_millis(70) {",
    b + "    if SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE).is_ok() {",
    b + "        last_geom = Some(geom);",
    b + "        last_move = std::time::Instant::now();",
    b + "        crate::mc_debug!(\"hud\", \"moved to {},{} {}x{} (crop {}x{})\", wx, wy, ww, wh, r.w, r.h);",
    b + "    }",
    b + "}",
    b + "if !shown || !IsWindowVisible(hwnd).as_bool() {",
    b + "    let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);",
    b + "    shown = true;",
    b + "}",
    b + "if !capturable {",
    b + "    let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);",
    b + "}",
    b + "",
    b + "let key = (ww, wh, cfg.thickness, cfg.show_label, cfg.brackets, label.clone());",
    b + "if last_paint_key.as_ref() != Some(&key) {",
    b + "    paint(hwnd, &label, cfg, Some((pad, pad, r.w, r.h)));",
    b + "    last_paint_key = Some(key);",
    b + "}",
    ind + "}",
    "",
]
lines[start:none_i] = body
src = "\n".join(lines)
src = src.replace("let mut last_paint_key: Option<(i32, i32, i32, i32, i32, bool, bool, String)> = None;",
                  "let mut last_paint_key: Option<(i32, i32, i32, bool, bool, String)> = None;")
# re-add the throttle state
i = next(i for i, l in enumerate(src.split("\n")) if "let mut last_geom" in l)
ls = src.split("\n")
ind0 = ls[i][:len(ls[i]) - len(ls[i].lstrip())]
ls[i+1:i+1] = [ind0 + "let mut last_move = std::time::Instant::now() - std::time::Duration::from_secs(1);"]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(ls))
print("reverted to the per-frame overlay")
