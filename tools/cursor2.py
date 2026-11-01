import io

# recorder (live + preview)
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\recorder.rs"
s = io.open(p, encoding="utf-8").read()
old = """            if let Some(spr) = sprites.get() {
                let sc = out_w as f32 / r.w as f32;
                draw(
                    &mut crop_buf,
                    out_w,
                    out_h,
                    (pos.x - r.x as f32) * sc,
                    (pos.y - r.y as f32) * sc,
                    sc,
                    spr,
                );"""
new = """            if let Some(spr) = sprites.get() {
                let sc = out_w as f32 / r.w as f32;
                // The viewport grows when the cursor moves fast, which shrinks
                // everything inside it - including the cursor. Scaling the sprite
                // by the same factor keeps it the size it has at rest, so it reads
                // as growing while the world pulls back.
                let grow = crate::camera::growth_factor(r.w as f32, out_w, s.zoom);
                draw(
                    &mut crop_buf,
                    out_w,
                    out_h,
                    (pos.x - r.x as f32) * sc,
                    (pos.y - r.y as f32) * sc,
                    sc * grow,
                    spr,
                );"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("recorder cursor scaled")
