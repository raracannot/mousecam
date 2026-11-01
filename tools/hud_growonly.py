import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
old = """    if win_w < qw || win_w > qw * 5 / 4 {
        win_w = qw.clamp(8, 16384);
    }
    if win_h < qh || win_h > qh * 5 / 4 {
        win_h = qh.clamp(8, 16384);
    }"""
new = """    // Grow only, and never shrink. Every resize recreates the layered surface
    // and forces the compositor to swallow a fresh bitmap; a shrinking crop would
    // otherwise resize the window ten times a second while the user drags
    // anything (the cursor feeds the camera). The surplus is colour-keyed, so a
    // window larger than the frame is invisible - it just costs one fixed
    // surface. Shrinking only happens when the monitor changes.
    if qw > win_w {
        win_w = qw.clamp(8, 16384);
    }
    if qh > win_h {
        win_h = qh.clamp(8, 16384);
    }"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("window size is now grow-only")
