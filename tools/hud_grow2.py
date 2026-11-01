import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
i = next(i for i, l in enumerate(lines) if "if win_w < qw" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
block = [
    ind + "// Grow only, never shrink. Every resize recreates the layered surface and",
    ind + "// makes the compositor swallow a fresh bitmap; a crop that breathes would",
    ind + "// otherwise reshape the window ten times a second whenever the cursor moves",
    ind + "// (i.e. while the user drags anything). The surplus is colour-keyed, so a",
    ind + "// window larger than the frame is invisible - it just costs one fixed surface.",
    ind + "if qw > win_w {",
    ind + "    win_w = qw.clamp(8, 16384);",
    ind + "}",
    ind + "if qh > win_h {",
    ind + "    win_h = qh.clamp(8, 16384);",
    ind + "}",
]
lines[i:i+6] = block
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("grow-only applied")
