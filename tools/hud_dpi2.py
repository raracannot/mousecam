import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for: %s" % (c, old[:120]))
    s = s.replace(old, new)

rep("""impl DeskMap {""",
"""impl DeskMap {
    /// No conversion at all: valid when this thread is per-monitor aware, in
    /// which case window coordinates are physical pixels and already line up
    /// with the monitor rectangles from DXGI.
    const fn identity() -> Self {
        Self { sx: 1.0, sy: 1.0, left: 0, top: 0, vx: 0, vy: 0 }
    }
""")

rep("""pub fn start() {""",
"""static HUD_AWARE: AtomicBool = AtomicBool::new(false);

pub fn start() {""")

rep("""            let m = DeskMap::new();""",
"""            // A single scale factor cannot describe two monitors with different
            // scaling, so prefer a per-monitor-aware thread, where the mapping is
            // the identity. Set before the window exists - awareness is fixed
            // per window once it has been created.
            let aware = unsafe {
                use windows::Win32::UI::HiDpi::{
                    SetThreadDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
                };
                SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2).is_ok()
            };
            HUD_AWARE.store(aware, Ordering::Relaxed);

            let m = if aware { DeskMap::identity() } else { DeskMap::new() };""")

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
