import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

def find(sub, start=0):
    for i in range(start, len(lines)):
        if sub in lines[i]:
            return i
    return -1

def ind(i):
    l = lines[i]
    return l[:len(l) - len(l.lstrip())]

# 1) awareness must be declared BEFORE the window exists (it is fixed per window)
i = find("let hwnd = match CreateWindowExW")
if i < 0:
    i = find("CreateWindowExW(")
    while i >= 0 and "let hwnd" not in lines[i]:
        i -= 1
assert i >= 0, "CreateWindowExW not found"
ind0 = ind(i)
lines[i:i] = [
    ind0 + "// DPI awareness is fixed for a window once it exists, so declare it here",
    ind0 + "// and not after the HWND is created.",
    ind0 + "unsafe {",
    ind0 + "    use windows::Win32::UI::HiDpi::{SetThreadDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2};",
    ind0 + "    let _ = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);",
    ind0 + "}",
]
print("1) awareness moved before window creation")

# 2) re-show if something hid the window (Win+D, a display change, ...)
i = find("if !shown {")
ind1 = ind(i)
lines[i] = ind1 + "if !shown || !IsWindowVisible(hwnd).as_bool() {"
print("2) visibility re-asserted")

# 3) honour SetWindowPos: only record the geometry when the call worked
i = find("let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE);")
ind2 = ind(i)
lines[i] = ind2 + "let placed = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE).is_ok();"
lines[i+1:i+1] = [ind2 + "if placed {"]
# close the block after the debug log line
j = find('"moved to {},{} {}x{} (crop {}x{})"', i)
j2 = find(");", j)
lines[j2+1:j2+1] = [ind2 + "}"]
# and make the bookkeeping conditional
k = find("last_geom = Some(geom);", i)
lines[k] = lines[k].replace("last_geom = Some(geom);", "last_geom = Some(geom);")
print("3) SetWindowPos result honoured")

# 4) repaint key: the label TEXT, not its length; and no repaint for pure moves
i = find("let key = (")
j = find(");", i)
key_lines = lines[i:j+1]
new_key = [
    ind(i) + "// The label is the only text on screen, so its content belongs in the key;",
    ind(i) + "// its length does not distinguish \"912x512\" from \"811x640\".",
    ind(i) + "let key = (",
    ind(i) + "    ww,",
    ind(i) + "    wh,",
    ind(i) + "    cfg.thickness,",
    ind(i) + "    cfg.show_label,",
    ind(i) + "    cfg.brackets,",
    ind(i) + "    label.clone(),",
    ind(i) + ");",
]
lines[i:j+1] = new_key

i = find("if last_paint_key != Some(key) || did_move {")
lines[i] = lines[i].replace("if last_paint_key != Some(key) || did_move {", "if last_paint_key.as_ref() != Some(&key) {")
print("4) repaint key uses the label text")

# the key type follows
i = find("let mut last_paint_key: Option<(i32, i32, i32, bool, bool, usize)> = None;")
lines[i] = lines[i].replace("Option<(i32, i32, i32, bool, bool, usize)>", "Option<(i32, i32, i32, bool, bool, String)>")

# 5) create failed / thread ended: let start() try again
i = find("let _ = ShowWindow(hwnd, SW_HIDE);", 380)
if i > 0:
    ind5 = ind(i)
    lines[i:i] = [ind5 + "STARTED.store(false, Ordering::SeqCst);"]
    print("5) STARTED cleared on exit")
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("hud.rs patched")
