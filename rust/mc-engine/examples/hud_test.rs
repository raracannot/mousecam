// Minimal HUD harness: shows the viewfinder frame for 8 seconds.
fn main() {
    unsafe {
        use windows::Win32::UI::HiDpi::{
            SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
        };
        let _ = SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    }
    mc_engine::hud::start();
    mc_engine::hud::set_rect(
        Some(mc_engine::IRect::new(1500, 620, 900, 500)),
        "900×500",
    );
    println!("hud shown; sleeping 8s");
    std::thread::sleep(std::time::Duration::from_secs(8));
    mc_engine::hud::set_rect(None, "");
    std::thread::sleep(std::time::Duration::from_millis(200));
    println!("done");
}
