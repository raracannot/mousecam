import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()
old = """fn already_running() -> bool {
    use windows::Win32::Foundation::{GetLastError, ERROR_ALREADY_EXISTS};
    use windows::Win32::System::Threading::CreateMutexW;
    unsafe {
        let _ = CreateMutexW(None, true, w!("Local\\\\MouseCamOverlay"));
        GetLastError() == ERROR_ALREADY_EXISTS
    }
}"""
new = """fn already_running() -> bool {
    // The window itself is the marker: while another overlay lives, its window
    // exists, and it cannot outlive its process. No extra kernel object needed.
    use windows::Win32::UI::WindowsAndMessaging::FindWindowW;
    unsafe { FindWindowW(w!("MouseCamHudProc"), windows::core::PCWSTR::null()).is_ok() }
}"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("singleton via the window class")
