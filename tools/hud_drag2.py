import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

def find(sub, start=0):
    for i in range(start, len(lines)):
        if sub in lines[i]:
            return i
    return -1

def ind_of(i):
    l = lines[i]
    return l[:len(l) - len(l.lstrip())]

# --- 1) throttle state next to last_geom
i = find("let mut last_geom: Option<(i32, i32, i32, i32)> = None;")
assert i >= 0, "last_geom not found"
ind = ind_of(i)
lines[i+1:i+1] = [
    ind + "let mut last_move = std::time::Instant::now() - std::time::Duration::from_secs(1);",
    ind + "let mut drag_logged = false;",
]

# --- 2) replace the move block
a = find("// Only move for a real change.")
b = find("if last_paint_key != Some(key) || resized {")
assert a > 0 and b > a, (a, b)
ind = ind_of(a)
block = [
    ind + "// Only move for a real change. During a window drag the cursor feeds",
    ind + "// the camera, so 1px of jitter would otherwise become a stream of",
    ind + "// SetWindowPos calls fighting the drag for the compositor - which is",
    ind + "// exactly when the preview turned into a black block. While the mouse",
    ind + "// button is held the window is left alone entirely, and otherwise it",
    ind + "// moves at most ~14 times a second.",
    ind + "let moved = match last_geom {",
    ind + "    Some(g) => {",
    ind + "        (g.0 - wx).abs() > 2",
    ind + "            || (g.1 - wy).abs() > 2",
    ind + "            || (g.2 - ww).abs() > 2",
    ind + "            || (g.3 - wh).abs() > 2",
    ind + "    }",
    ind + "    None => true,",
    ind + "};",
    ind + "let dragging = unsafe {",
    ind + "    use windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;",
    ind + "    (GetAsyncKeyState(0x01) as u16 & 0x8000) != 0",
    ind + "};",
    ind + "let mut did_move = false;",
    ind + "if moved && !dragging && last_move.elapsed() >= std::time::Duration::from_millis(70) {",
    ind + "    let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE);",
    ind + "    last_geom = Some(geom);",
    ind + "    last_move = std::time::Instant::now();",
    ind + "    did_move = true;",
    ind + "    crate::mc_debug!(\"hud\", \"moved to {},{} {}x{} (crop {}x{})\", wx, wy, ww, wh, r.w, r.h);",
    ind + "} else if moved && dragging && !drag_logged {",
    ind + "    drag_logged = true;",
    ind + "    crate::mc_debug!(\"hud\", \"holding still while the mouse button is down\");",
    ind + "}",
    ind + "if !dragging {",
    ind + "    drag_logged = false;",
    ind + "}",
    "",
]
lines[a:b] = block

# --- 3) paint only when the window actually moved
b2 = find("if last_paint_key != Some(key) || resized {")
assert b2 > 0
lines[b2] = lines[b2].replace("|| resized {", "|| did_move {")

io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("hud drag freeze + throttle applied")
