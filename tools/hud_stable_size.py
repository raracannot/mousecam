import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

def find(sub, start=0):
    for i in range(start, len(lines)):
        if sub in lines[i]:
            return i
    return -1

def ind(i):
    l = lines[i]
    return l[:len(l) - len(l.lstrip())]

# state that survives iterations
i = find("let mut last_geom: Option<(i32, i32, i32, i32)> = None;")
ind0 = ind(i)
lines[i+1:i+1] = [
    ind0 + "// The window is allowed to be larger than the frame: the colour key makes",
    ind0 + "// the excess invisible. Resizing a layered window recreates and repaints its",
    ind0 + "// whole surface, so it must happen rarely - moving is the cheap operation.",
    ind0 + "let mut win_w: i32 = 0;",
    ind0 + "let mut win_h: i32 = 0;",
]

# replace the geometry computation
a = find("let (wx, wy) = m.pt(r.x - pad, r.y - pad);")
b = find("let wh = wh.clamp(1, 16384);")
assert a > 0 and b > a, (a, b)
ind1 = ind(a)
block = [
    ind1 + "let need_w = (r.w + pad * 2).max(8);",
    ind1 + "let need_h = (r.h + pad * 2).max(8);",
    ind1 + "// Grow in 64 px steps; only give space back when the frame no longer",
    ind1 + "// needs most of it. Quantising is what keeps a zooming camera from",
    ind1 + "// resizing the layered surface ten times a second.",
    ind1 + "let qw = ((need_w + 63) / 64) * 64;",
    ind1 + "let qh = ((need_h + 63) / 64) * 64;",
    ind1 + "if win_w < qw || win_w > qw * 5 / 4 {",
    ind1 + "    win_w = qw.clamp(8, 16384);",
    ind1 + "}",
    ind1 + "if win_h < qh || win_h > qh * 5 / 4 {",
    ind1 + "    win_h = qh.clamp(8, 16384);",
    ind1 + "}",
    ind1 + "let off_x = ((win_w - need_w) / 2).max(0);",
    ind1 + "let off_y = ((win_h - need_h) / 2).max(0);",
    ind1 + "let (wx, wy) = m.pt(r.x - pad - off_x, r.y - pad - off_y);",
    ind1 + "let (ww, wh) = (win_w, win_h);",
]
lines[a:b+1] = block

# the frame is drawn at its offset inside the window, not at the client corner
src = "\n".join(lines)
old_cx = "let cx = (pad as f32 / m.sx).round() as i32;"
old_cy = "let cy = (pad as f32 / m.sy).round() as i32;"
assert src.count(old_cx) == 1 and src.count(old_cy) == 1
src = src.replace(old_cx, "let cx = ((off_x + pad) as f32 / m.sx).round() as i32;")
src = src.replace(old_cy, "let cy = ((off_y + pad) as f32 / m.sy).round() as i32;")
io.open(p, "w", encoding="utf-8", newline="").write(src)
print("layered-window resizes quantised")
