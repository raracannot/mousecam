import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\capture.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:90]))
    s = s.replace(old, new)

# ---- Dda: remember an unusable surface format instead of silently freezing
rep("""    /// Set when the duplication died (display change, UAC, a fullscreen
    /// app taking the output). The owner reopens instead of failing forever.
    lost: bool,""",
"""    /// Set when the duplication died (display change, UAC, a fullscreen
    /// app taking the output). The owner reopens instead of failing forever.
    lost: bool,
    /// Set when the desktop handed us a surface we cannot map - HDR / 10-bit
    /// displays return R16G16B16A16_FLOAT. Silently returning the previous
    /// frame would record a frozen picture for the whole session.
    unsupported_format: Option<u32>,""")

rep("""                    if d.Format == DXGI_FORMAT_B8G8R8A8_UNORM {""",
"""                    if d.Format != DXGI_FORMAT_B8G8R8A8_UNORM {
                        if self.unsupported_format.is_none() {
                            self.unsupported_format = Some(d.Format.0 as u32);
                        }
                    }
                    if d.Format == DXGI_FORMAT_B8G8R8A8_UNORM {""")

# ---- clamp the copy to the surface we actually mapped (fixes the OOB read)
rep("""            if pitch == (w as usize) * 4 {
                std::ptr::copy_nonoverlapping(
                    src,
                    dst.as_mut_ptr() as *mut u8,
                    (w as usize) * (h as usize) * 4,
                );
            } else {
                let row_bytes = (w as usize) * 4;
                let dptr = dst.as_mut_ptr() as *mut u8;
                for y in 0..h as usize {
                    std::ptr::copy_nonoverlapping(
                        src.add(y * pitch),
                        dptr.add(y * row_bytes),
                        row_bytes,
                    );
                }
            }""",
"""            // The staging texture is rebuilt when the display changes size, but
            // `w`/`h` come from the monitor rect captured at open() time. If the
            // surface shrank, copying w*h from it reads past the mapping, so the
            // copy is clamped to the surface that was actually mapped.
            let copy_w = (w as usize).min(self.scr_w as usize).min(pitch / 4);
            let copy_h = (h as usize).min(self.scr_h as usize);
            let row_bytes = copy_w * 4;
            let dptr = dst.as_mut_ptr() as *mut u8;
            for y in 0..copy_h {
                std::ptr::copy_nonoverlapping(src.add(y * pitch), dptr.add(y * w as usize * 4), row_bytes);
            }
            if copy_w != w as usize || copy_h != h as usize {
                self.resized = true;
            }""")

rep("""    lost: bool,
    /// Set when the desktop handed us a surface we cannot map""",
"""    lost: bool,
    /// The surface no longer matches the monitor rect, so the previous frame is
    /// only partially filled. The owner should reopen the capture.
    resized: bool,
    /// Set when the desktop handed us a surface we cannot map""")

s = s.replace("""            have_frame: false,
            lost: false,""",
"""            have_frame: false,
            lost: false,
            resized: false,""", 1)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("format detection + clamped copy")
