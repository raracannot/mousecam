import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()

old = """pub fn main() -> i32 {
    if already_running() {
        return 0;
    }"""
new = """pub fn main() -> i32 {
    if already_running() {
        return 0;
    }

    // This process never runs Tauri, so nothing has told Windows what it is. A
    // process with no DPI awareness gets its coordinates virtualised: the window
    // lands somewhere else and is drawn at the scaled size, which looks exactly
    // like the frame being wrong. The parent works in physical pixels, so the
    // overlay must too.
    let log_path = std::env::var("MC_HUD_LOG")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::current_exe()
                .ok()
                .and_then(|p| p.parent().map(|d| d.join("mousecam.hud.log")))
                .unwrap_or_else(|| std::path::PathBuf::from("mousecam.hud.log"))
        });
    crate::log::init(&log_path, true);

    unsafe {
        use windows::Win32::UI::HiDpi::{
            SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
        };
        match SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2) {
            Ok(()) => crate::mc_info!("hud-proc", "dpi awareness set to per-monitor-v2"),
            Err(e) => crate::mc_warn!("hud-proc", "could not set dpi awareness: {e}"),
        }
    }"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)

# log what the child is asked to draw, so a mismatch can be traced end to end
old2 = """        Some("frame") => {
            let rest: Vec<&str> = it.collect();"""
new2 = """        Some("frame") => {
            let rest: Vec<&str> = it.collect();
            crate::mc_debug!("hud-proc", "frame {}", rest.join(" "));"""
assert s.count(old2) == 1
s = s.replace(old2, new2)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("child is now dpi aware and logs its input")
