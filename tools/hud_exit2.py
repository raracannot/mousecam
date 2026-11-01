import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
old = """    let _ = windows::Win32::UI::WindowsAndMessaging::DestroyWindow(hwnd);
    let _ = windows::Win32::UI::WindowsAndMessaging::UnregisterClassW(w!("MouseCamHud"), GetModuleHandleW(None).unwrap_or_default());
    STARTED.store(false, Ordering::SeqCst);"""
new = """    let _ = windows::Win32::UI::WindowsAndMessaging::DestroyWindow(hwnd);
    let hinst = GetModuleHandleW(None).unwrap_or_default();
    let _ = windows::Win32::UI::WindowsAndMessaging::UnregisterClassW(w!("MouseCamHud"), Some(hinst.into()));
    STARTED.store(false, Ordering::SeqCst);"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("fixed")
