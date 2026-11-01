import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# 1) state carries the recorded monitor: the overlay is a fixed slab over it
rep("""struct HudState {
    rect: Option<IRect>,
    label: String,
    enabled: bool,
    cfg: HudConfig,
}""",
"""struct HudState {
    rect: Option<IRect>,
    /// Display being recorded. The overlay is a fixed slab covering it, so the
    /// frame can follow the camera by repainting instead of by moving a window.
    monitor: Option<IRect>,
    label: String,
    enabled: bool,
    cfg: HudConfig,
}""")

rep("""        Mutex::new(HudState {
            rect: None,
            label: String::new(),""",
"""        Mutex::new(HudState {
            rect: None,
            monitor: None,
            label: String::new(),""")

# 2) pass the monitor through instead of dropping it
rep("""pub fn set_frame(rect: Option<IRect>, _monitor: Option<IRect>, label: &str) {
    set_rect(rect, label);
}""",
"""pub fn set_frame(rect: Option<IRect>, monitor: Option<IRect>, label: &str) {
    set_rect(rect, label);
    if let Ok(mut g) = state().lock() {
        g.monitor = monitor;
    }
}""")

# 3) the loop sees it
rep("""            let g = state().lock().unwrap();
            (g.rect, g.enabled, g.label.clone(), g.cfg)""",
"""            let g = state().lock().unwrap();
            (g.rect, g.enabled, g.label.clone(), g.cfg, g.monitor)""")
rep("        let (rect, enabled, label, cfg) = {", "        let (rect, enabled, label, cfg, mon) = {")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("monitor plumbed through the HUD state")
