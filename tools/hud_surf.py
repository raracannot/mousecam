import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# state for the slab size
i = next(i for i, l in enumerate(lines) if "let mut surf: Option<Surface> = None;" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines[i:i] = [
    ind + "// The surface is reused across frames: allocating a 7 MB DIB whenever",
    ind + "// the crop changes size (ten times a second while the camera moves) both",
    ind + "// wastes memory and can fail, which froze the overlay for good.",
    ind + "let mut win_w: i32 = 0;",
    ind + "let mut win_h: i32 = 0;",
]

start = next(i for i, l in enumerate(lines) if l.strip() == "Some(r) => {")
none_i = next(i for i in range(start, len(lines)) if lines[i].strip() == "None => {")
ind = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
b = ind + "    "

body = [
    ind + "Some(r) => {",
    b + "let pad = cfg.thickness.clamp(1, 8) + 2;",
    b + "let need_w = r.w + pad * 2;",
    b + "let need_h = r.h + pad * 2;",
    b + "",
    b + "// Grow the surface in 64 px steps, never shrink: the surplus is fully",
    b + "// transparent (per-pixel alpha), so a surface larger than the frame is",
    b + "// invisible, and reallocating it constantly is what used to freeze the",
    b + "// overlay.",
    b + "let qw = (((need_w + 63) / 64) * 64).clamp(64, 8192);",
    b + "let qh = (((need_h + 63) / 64) * 64).clamp(64, 8192);",
    b + "if qw > win_w {",
    b + "    win_w = qw;",
    b + "}",
    b + "if qh > win_h {",
    b + "    win_h = qh;",
    b + "}",
    b + "let off_x = ((win_w - need_w) / 2).max(0);",
    b + "let off_y = ((win_h - need_h) / 2).max(0);",
    b + "",
    b + "let (wx, wy) = m.pt(r.x - pad - off_x, r.y - pad - off_y);",
    b + "let (ww, wh) = (win_w, win_h);",
    b + "let geom = (wx, wy, ww, wh);",
    b + "",
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
    b + "let due = !dragging && last_move.elapsed() >= std::time::Duration::from_millis(70);",
    b + "",
    b + "let key = (ww, wh, off_x, off_y, cfg.thickness, cfg.show_label, cfg.brackets, label.clone());",
    b + "let stale = surf.as_ref().map(|s| (s.w, s.h) != (ww, wh)).unwrap_or(true);",
    b + "if stale {",
    b + "    surf = Surface::new(ww, wh);",
    b + "    if surf.is_none() {",
    b + "        crate::mc_warn!(\"hud\", \"could not allocate a {}x{} surface\", ww, wh);",
    b + "    }",
    b + "}",
    b + "if let Some(s) = surf.as_mut() {",
    b + "    if (moved || last_paint_key.as_ref() != Some(&key)) && due {",
    b + "        let fx = off_x + pad;",
    b + "        let fy = off_y + pad;",
    b + "        if paint(hwnd, s, wx, wy, &label, cfg, Some((fx, fy, r.w, r.h))) {",
    b + "            last_paint_key = Some(key);",
    b + "            last_geom = Some(geom);",
    b + "            last_move = std::time::Instant::now();",
    b + "            crate::mc_debug!(\"hud\", \"overlay at {},{} {}x{} frame {}x{}\", wx, wy, ww, wh, r.w, r.h);",
    b + "        } else {",
    b + "            crate::mc_debug!(\"hud\", \"UpdateLayeredWindow failed, retrying\");",
    b + "        }",
    b + "    }",
    b + "}",
    b + "if surf.is_some() {",
    b + "    if !shown || !IsWindowVisible(hwnd).as_bool() {",
    b + "        let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);",
    b + "        shown = true;",
    b + "    }",
    b + "    if !capturable {",
    b + "        let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);",
    b + "    }",
    b + "}",
    ind + "}",
    "",
]
lines[start:none_i] = body
src = "\n".join(lines)
src = src.replace("Option<(i32, i32, i32, bool, bool, String)>", "Option<(i32, i32, i32, i32, i32, bool, bool, String)>")
io.open(p, "w", encoding="utf-8", newline="").write(src)
print("surface is now reused and grow-only")
