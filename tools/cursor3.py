import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\render.rs"
s = io.open(p, encoding="utf-8").read()
old = """            let mpt: Vec2 = cursor_at(&clip.track, edit, target as f64 / s.fps as f64);
            let sc = out_w as f32 / rw as f32;
            draw(
                &mut crop_buf,
                out_w,
                out_h,
                (mpt.x - r.x as f32) * sc,
                (mpt.y - r.y as f32) * sc,
                sc,
                spr,
            );"""
new = """            let mpt: Vec2 = cursor_at(&clip.track, edit, target as f64 / s.fps as f64);
            let sc = out_w as f32 / rw as f32;
            // same rule as the live recorder, taken from the baked rect so an
            // export matches what was on screen while recording
            let grow = crate::camera::growth_factor(rw as f32, out_w, s.zoom);
            draw(
                &mut crop_buf,
                out_w,
                out_h,
                (mpt.x - r.x as f32) * sc,
                (mpt.y - r.y as f32) * sc,
                sc * grow,
                spr,
            );"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("render cursor scaled")
