import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

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
    b + "// Throttle and skip while a window is being dragged: there is no point",
    b + "// repainting the overlay 60 times a second, and the camera is only",
    b + "// interesting when the cursor actually settles.",
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
    b + "let key = (ww, wh, cfg.thickness, cfg.show_label, cfg.brackets, label.clone());",
    b + "let stale = surf.as_ref().map(|s| (s.w, s.h) != (ww, wh)).unwrap_or(true);",
    b + "if stale {",
    b + "    surf = Surface::new(ww, wh);",
    b + "}",
    b + "if let Some(s) = surf.as_mut() {",
    b + "    if (moved || last_paint_key.as_ref() != Some(&key)) && due {",
    b + "        // UpdateLayeredWindow positions the window as well, and the",
    b + "        // surface it is given is exactly what we drew - there is no",
    b + "        // colour key to leave an unpainted area black.",
    b + "        if paint(hwnd, s, wx, wy, &label, cfg, Some((pad, pad, r.w, r.h))) {",
    b + "            last_paint_key = Some(key);",
    b + "            last_geom = Some(geom);",
    b + "            last_move = std::time::Instant::now();",
    b + "            crate::mc_debug!(\"hud\", \"{},{}\" + \" {}x{} (crop {}x{})\", wx, wy, ww, wh, r.w, r.h);",
    b + "        }",
    b + "    }",
    b + "}",
    b + "if let Some(_) = surf.as_ref() {",
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
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("loop rewritten for ULW")
