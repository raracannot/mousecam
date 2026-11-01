import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

i = next(i for i, l in enumerate(lines) if "if last_paint_key != Some(key) || did_move {" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
key_block = [
    ind + "// Repaint when the appearance or the geometry changed.",
    ind + "let key = (",
    ind + "    ww,",
    ind + "    wh,",
    ind + "    cfg.thickness,",
    ind + "    cfg.show_label,",
    ind + "    cfg.brackets,",
    ind + "    label.len(),",
    ind + ");",
]
lines[i:i] = key_block
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("key restored")
