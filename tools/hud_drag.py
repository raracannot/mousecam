import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for: %s" % (c, old[:160]))
    s = s.replace(old, new)

# state for the throttle
rep("            let mut last_geom: Option<(i32, i32, i32, i32)> = None;",
    "            let mut last_geom: Option<(i32, i32, i32, i32)> = None;\n"
    "            let mut last_move = std::time::Instant::now() - std::time::Duration::from_secs(1);")

old_move = s[s.index("                // Only move for a real change."):s.index("                if last_paint_key != Some(key) || resized {")]
new_move = '''                // Only move for a real change. During a window drag the cursor
                // feeds the camera, so 1px of jitter would otherwise become a
                // stream of SetWindowPos calls fighting the drag for the
                // compositor - which is what turned the preview into a black
                // block. While the mouse button is held we do not touch the
                // window at all, and otherwise move at most ~14 times a second.
                let moved = match last_geom {
                    Some(g) => {
                        (g.0 - wx).abs() > 2
                            || (g.1 - wy).abs() > 2
                            || (g.2 - ww).abs() > 2
                            || (g.3 - wh).abs() > 2
                    }
                    None => true,
                };
                let dragging = unsafe {
                    use windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;
                    (GetAsyncKeyState(0x01) as u16 & 0x8000) != 0
                };
                let ready = last_move.elapsed() >= std::time::Duration::from_millis(70);
                let mut did_move = false;
                if moved && !dragging && ready {
                    let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE);
                    last_geom = Some(geom);
                    last_move = std::time::Instant::now();
                    did_move = true;
                    crate::mc_debug!(
                        "hud",
                        "moved to {},{} {}x{} (crop {}x{})",
                        wx, wy, ww, wh, r.w, r.h
                    );
                } else if moved && dragging && moved_reported {
                    // once per drag, so the log shows a drag happened
                    crate::mc_debug!("hud", "holding still while the mouse button is down");
                    moved_reported = false;
                }

'''
s = s.replace(old_move, new_move)
s = s.replace("                if last_paint_key != Some(key) || resized {",
              "                if last_paint_key != Some(key) || did_move {")
s = s.replace("            let mut last_move = std::time::Instant::now() - std::time::Duration::from_secs(1);",
              "            let mut last_move = std::time::Instant::now() - std::time::Duration::from_secs(1);\n"
              "            let mut moved_reported = true;")
s = s.replace("                    moved_reported = false;\n                }", "                    moved_reported = false;\n                }\n                if !dragging {\n                    moved_reported = true;\n                }")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("hud drag freeze + throttle")
