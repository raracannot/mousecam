import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = """fn main() {
    // NOTE: never call SetProcessDpiAwarenessContext here."""
new = """/// 0 unaware, 1 system, 2 per-monitor. Logged because a mis-declared process
/// gets bitmap-stretched across displays with different scaling, which is what
/// makes WebView2 hang when the window is dragged to another monitor.
fn log_dpi_awareness() {
    use windows::Win32::UI::HiDpi::{GetAwarenessFromDpiAwarenessContext, GetThreadDpiAwarenessContext};
    unsafe {
        let ctx = GetThreadDpiAwarenessContext();
        let a = GetAwarenessFromDpiAwarenessContext(ctx);
        log(&format!("dpi awareness = {} ({:?})", a.0, a));
    }
}

fn main() {
    // NOTE: never call SetProcessDpiAwarenessContext here."""
assert s.count(old) == 1
s = s.replace(old, new)

old2 = """    tauri::Builder::default()
        .setup(|app| {"""
new2 = """    log_dpi_awareness();
    tauri::Builder::default()
        .setup(|app| {"""
assert s.count(old2) == 1
s = s.replace(old2, new2)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("dpi logging added")
