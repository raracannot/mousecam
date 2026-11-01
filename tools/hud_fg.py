import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# helper: is one of OUR windows holding the foreground?
rep("""static HUD_AWARE: AtomicBool""",
"""/// True when the foreground window belongs to this process (and is not the
/// overlay itself). The overlay is hidden then: it is only useful while another
/// application is being recorded, and keeping a topmost layered window parked
/// over our own WebView2 window is exactly the interaction that made the UI
/// stop composing.
unsafe fn app_in_foreground(hud: windows::Win32::Foundation::HWND) -> bool {
    use windows::Win32::UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowThreadProcessId};
    let fg = GetForegroundWindow();
    if fg.is_invalid() || fg == hud {
        return false;
    }
    let mut pid = 0u32;
    GetWindowThreadProcessId(fg, Some(&mut pid));
    pid == std::process::id()
}

static HUD_AWARE: AtomicBool""")

# gate the overlay on it
rep("""        let want = match rect {
            Some(r) if enabled && r.w > 8 && r.h > 8 => Some(r),
            _ => None,
        };""",
"""        let want = match rect {
            Some(r) if enabled && r.w > 8 && r.h > 8 && !unsafe { app_in_foreground(hwnd) } => {
                Some(r)
            }
            _ => None,
        };""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("overlay hidden while MouseCam has focus")
