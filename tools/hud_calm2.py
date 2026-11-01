import io, re
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# find the geometry-change branch
idx = [i for i, l in enumerate(lines) if l.strip() == "if last_geom != Some(geom) {"]
print("branch candidates:", idx)
if not idx:
    raise SystemExit("branch not found")
i = idx[0]
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
print("indent =", len(ind))

# the block is: if ... { SetWindowPos; last_geom = ...; }
j = i
depth = 0
while j < len(lines):
    depth += lines[j].count("{") - lines[j].count("}")
    if depth == 0 and j > i:
        break
    j += 1
print("block spans", i, "..", j)
print("\n".join(lines[i:j+1]))

block = [
    ind + "// Only move for a real change. During a window drag the cursor feeds",
    ind + "// the camera, so 1px of jitter would otherwise become a stream of",
    ind + "// SetWindowPos calls fighting the drag for the compositor.",
    ind + "let moved = match last_geom {",
    ind + "    Some(g) => {",
    ind + "        (g.0 - wx).abs() > 2",
    ind + "            || (g.1 - wy).abs() > 2",
    ind + "            || (g.2 - ww).abs() > 2",
    ind + "            || (g.3 - wh).abs() > 2",
    ind + "    }",
    ind + "    None => true,",
    ind + "};",
    ind + "if moved || resized {",
    ind + "    let _ = SetWindowPos(hwnd, Some(HWND_TOPMOST), wx, wy, ww, wh, SWP_NOACTIVATE);",
    ind + "    last_geom = Some(geom);",
    ind + "    crate::mc_debug!(\"hud\", \"moved to {},{} {}x{} (crop {}x{})\", wx, wy, ww, wh, r.w, r.h);",
    ind + "}",
]
lines[i:j+1] = block
src = "\n".join(lines)

# a boundary rectangle does not need 80 Hz
src, n = re.subn(r"std::thread::sleep\(std::time::Duration::from_millis\(\d+\)\);",
                 "std::thread::sleep(std::time::Duration::from_millis(33));", src)
print("sleep replaced:", n)
io.open(p, "w", encoding="utf-8", newline="").write(src)
print("done")
