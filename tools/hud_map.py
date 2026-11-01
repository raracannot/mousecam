import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# 1) drop the shadowing binding that undid the per-monitor-aware mapping
i = next(i for i, l in enumerate(lines) if l.strip() == "let m = DeskMap::new();" and i > 290)
assert "while STARTED" in "\n".join(lines[max(0, i-8):i]), "not the loop-local binding"
del lines[i]
print("shadowing binding removed at", i + 1)

# 2) keep it mutable so a non-aware fallback can still be refreshed
j = next(j for j, l in enumerate(lines) if "let m = if aware { DeskMap::identity() } else { DeskMap::new() };" in l)
lines[j] = lines[j].replace("let m =", "let mut m =")
ind = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
lines[j+1:j+1] = [
    ind + "// Only the fallback needs a refresh; the identity mapping is constant and",
    ind + "// enumerating the displays 30 times a second just costs syscalls.",
    ind + "let mut map_tick: u32 = 0;",
]

# 3) refresh occasionally when we had to fall back
k = next(k for k, l in enumerate(lines) if "let want = match rect {" in l)
ind2 = lines[k][:len(lines[k]) - len(lines[k].lstrip())]
lines[k:k] = [
    ind2 + "map_tick = map_tick.wrapping_add(1);",
    ind2 + "if !aware && map_tick % 150 == 0 {",
    ind2 + "    m = DeskMap::new();",
    ind2 + "}",
    "",
]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("mapping cached")
