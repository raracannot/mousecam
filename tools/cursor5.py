import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\camera.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# the derive lost its struct and the helper lost its tail; rebuild the block
start = next(i for i, l in enumerate(lines) if l.startswith("#[derive(Clone, Copy, Debug, Default)]"))
end = next(i for i in range(start, len(lines)) if l.strip() == "fn clampf(v: f32, a: f32, b: f32) -> f32 {")
block = [
    "#[derive(Clone, Copy, Debug, Default)]",
    "pub struct CamSnapshot {",
    "    pub cursor: Vec2,",
    "    pub center: Vec2,",
    "    pub src_w: f32,",
    "    pub src_h: f32,",
    "    pub speed: f32,",
    "    pub expand: f32,",
    "    pub valid: bool,",
    "    pub tracking: bool,",
    "}",
    "",
    "/// How much the viewport is currently grown by speed, relative to its resting",
    "/// size at this zoom. Derived from the rect itself so the live recorder and the",
    "/// export bake the same number.",
    "pub fn growth_factor(src_w: f32, out_w: i32, zoom: f32) -> f32 {",
    "    let rest = out_w as f32 / zoom.clamp(0.1, 8.0);",
    "    if rest <= 0.0 {",
    "        return 1.0;",
    "    }",
    "    (src_w / rest).clamp(1.0, 4.0)",
    "}",
    "",
]
lines[start:end] = block
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("block rebuilt")
