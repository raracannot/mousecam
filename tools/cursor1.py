import io

# 1) a shared helper so live recording and export agree exactly
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\camera.rs"
s = io.open(p, encoding="utf-8").read()
anchor = "/// One downscaled follow-cam frame"
if anchor not in s:
    anchor = "pub struct CamSnapshot {"
i = s.index(anchor)
helper = '''/// How much the viewport is currently grown by speed, relative to its resting
/// size at this zoom. Derived from the rect itself so the live recorder and the
/// export bake the same number.
pub fn growth_factor(src_w: f32, out_w: i32, zoom: f32) -> f32 {
    let rest = out_w as f32 / zoom.clamp(0.1, 8.0);
    if rest <= 0.0 {
        return 1.0;
    }
    (src_w / rest).clamp(1.0, 4.0)
}

'''
s = s[:i] + helper + s[i:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("growth_factor added")
