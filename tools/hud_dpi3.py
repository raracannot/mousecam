import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# locate the call
idx = [i for i, l in enumerate(lines) if "DeskMap::new()" in l and "=>" not in l]
print("candidates:", [(i, repr(lines[i])) for i in idx])
target = None
for i in idx:
    indent = len(lines[i]) - len(lines[i].lstrip())
    if indent >= 8:
        target = i
        break
print("picked:", target, repr(lines[target]) if target is not None else None)

src = "\n".join(lines)

# 1) identity constructor
anchor = "impl DeskMap {"
assert src.count(anchor) == 1
src = src.replace(anchor, """impl DeskMap {
    /// No conversion at all: valid when this thread is per-monitor aware, in
    /// which case window coordinates are physical pixels and already line up
    /// with the monitor rectangles from DXGI.
    const fn identity() -> Self {
        Self { sx: 1.0, sy: 1.0, left: 0, top: 0, vx: 0, vy: 0 }
    }
""")

# 2) awareness flag
assert src.count("pub fn start() {") == 1
src = src.replace("pub fn start() {", "static HUD_AWARE: AtomicBool = AtomicBool::new(false);\n\npub fn start() {")

# 3) choose the mapping, by exact indentation
lines = src.split("\n")
if target is None:
    raise SystemExit("no indented DeskMap::new() found")
ind = lines[target][:len(lines[target]) - len(lines[target].lstrip())]
lines[target] = (
    ind + "// A single scale factor cannot describe two monitors with different scaling, so\n"
    + ind + "// prefer a per-monitor-aware thread, where the mapping is the identity. Set\n"
    + ind + "// before the window exists - awareness is fixed per window once created.\n"
    + ind + "let aware = unsafe {\n"
    + ind + "    use windows::Win32::UI::HiDpi::{\n"
    + ind + "        SetThreadDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,\n"
    + ind + "    };\n"
    + ind + "    SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2).is_ok()\n"
    + ind + "};\n"
    + ind + "HUD_AWARE.store(aware, Ordering::Relaxed);\n"
    + ind + "let m = if aware { DeskMap::identity() } else { DeskMap::new() };"
)
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("patched ok")
