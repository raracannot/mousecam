import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# 1) the killer: clearing STARTED inside the hide branch ends the HUD thread, so
#    the next toggle spawns a second thread and a second window while the old
#    one is orphaned - that is the "does not draw any more / takes ages" report.
n = 0
for i, l in enumerate(lines):
    if l.strip() == "STARTED.store(false, Ordering::SeqCst);" and i > 300:
        del lines[i]
        n += 1
        break
print("removed misplaced STARTED clear:", n)

src = "\n".join(lines)

# 2) focus gate off
old = """        let want = match rect {
            Some(r) if enabled && r.w > 8 && r.h > 8 && !unsafe { app_in_foreground(hwnd) } => {
                Some(r)
            }
            _ => None,
        };"""
new = """        let want = match rect {
            Some(r) if enabled && r.w > 8 && r.h > 8 => Some(r),
            _ => None,
        };"""
if old in src:
    src = src.replace(old, new)
    print("focus gate removed")

# 3) clean exit so a restart starts from scratch instead of leaving an orphan
old_exit = """    let _ = ShowWindow(hwnd, SW_HIDE);
    let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), 0, 0, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE);
}"""
new_exit = """    let _ = ShowWindow(hwnd, SW_HIDE);
    // Tear the window down: start() can be called again, and an orphaned window
    // from a dead thread keeps drawing stale pixels over the desktop.
    let _ = windows::Win32::UI::WindowsAndMessaging::DestroyWindow(hwnd);
    let _ = windows::Win32::UI::WindowsAndMessaging::UnregisterClassW(w!("MouseCamHud"), GetModuleHandleW(None).unwrap_or_default());
    STARTED.store(false, Ordering::SeqCst);
}"""
if old_exit in src:
    src = src.replace(old_exit, new_exit)
    print("clean shutdown on exit")
io.open(p, "w", encoding="utf-8", newline="").write(src)
