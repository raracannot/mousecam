import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

start = next(i for i, l in enumerate(lines) if l.strip() == "match want {")
# the Some(r) arm runs until the line that closes it (same indent as "Some(r) => {")
open_i = next(i for i in range(start, len(lines)) if lines[i].strip() == "Some(r) => {")
ind = lines[open_i][:len(lines[open_i]) - len(lines[open_i].lstrip())]
close_i = next(i for i in range(open_i + 1, len(lines)) if lines[i].strip() == "}" and lines[i].startswith(ind) and len(lines[i]) - len(lines[i].lstrip()) == len(ind))
print("replacing lines", open_i + 1, "..", close_i + 1)

b = ind          # base indent inside arms
body = [
    ind + "let pad = cfg.thickness.clamp(1, 8) + 2;",
    "",
    ind + "// The overlay is a FIXED slab covering the display being recorded; the",
    ind + "// frame is drawn inside it. Following the camera therefore never moves or",
    ind + "// resizes the window - moving a large layered window while the user drags",
    ind + "// anything is what wedged the desktop compositor (black block, hang).",
    ind + "let slab = mon.unwrap_or(r);",
    ind + "let (sx0, sy0) = (slab.x, slab.y);",
    ind + "let (sw, sh) = (slab.w.max(64), slab.h.max(64));",
    ind + "let want_geom = (sx0, sy0, sw, sh);",
    "",
    ind + "if last_geom != Some(want_geom) {",
    ind + "    let (wx, wy) = m.pt(sx0, sy0);",
    ind + "    let (ww, wh) = m.len(sw, sh);",
    ind + "    if SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE).is_ok() {",
    ind + "        last_geom = Some(want_geom);",
    ind + "        crate::mc_debug!(\"hud\", \"slab {}x{} at {},{} for display {}x{}\", ww, wh, wx, wy, sw, sh);",
    ind + "    }",
    ind + "}",
    ind + "if !shown || !IsWindowVisible(hwnd).as_bool() {",
    ind + "    let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);",
    ind + "    shown = true;",
    ind + "}",
    ind + "// Must come after ShowWindow: while the window is hidden the call succeeds",
    ind + "// but the affinity stays WDA_NONE and the frame ends up in the recording.",
    ind + "if !capturable {",
    ind + "    let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);",
    ind + "}",
    "",
    ind + "// The frame, in client pixels. paint() clears the whole client to the colour",
    ind + "// key first, so the previous frame is erased as part of drawing the new one.",
    ind + "let fx = ((r.x - sx0 - pad) as f32 / m.sx).round() as i32;",
    ind + "let fy = ((r.y - sy0 - pad) as f32 / m.sy).round() as i32;",
    ind + "let fw = (r.w as f32 / m.sx).round() as i32;",
    ind + "let fh = (r.h as f32 / m.sy).round() as i32;",
    ind + "let key = (fx, fy, fw, fh, cfg.thickness, cfg.show_label, cfg.brackets, label.clone());",
    ind + "if last_paint_key.as_ref() != Some(&key) {",
    ind + "    paint(hwnd, &label, cfg, Some((fx, fy, fw, fh)));",
    ind + "    last_paint_key = Some(key);",
    ind + "}",
]
lines[open_i:close_i+1] = body

src = "\n".join(lines)
src = src.replace("let mut last_paint_key: Option<(i32, i32, i32, bool, bool, String)> = None;",
                  "let mut last_paint_key: Option<(i32, i32, i32, i32, i32, bool, bool, String)> = None;")
# these are only used by the old move loop
for dead in ["let mut last_move = std::time::Instant::now() - std::time::Duration::from_secs(1);",
             "let mut drag_logged = false;",
             "let mut win_w: i32 = 0;", "let mut win_h: i32 = 0;"]:
    src = src.replace("            " + dead + "\n", "")
io.open(p, "w", encoding="utf-8", newline="").write(src)
print("static-slab overlay installed")
