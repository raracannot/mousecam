import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

a = next(i for i, l in enumerate(lines) if l.strip() == "if !shown {")
b = next(i for i in range(a, len(lines)) if lines[i].strip() == "}" and "SetWindowDisplayAffinity" in lines[i-1])
ind = lines[a][:len(lines[a]) - len(lines[a].lstrip())]
new = [
    ind + "if !shown {",
    ind + "    let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);",
    ind + "    shown = true;",
    ind + "}",
    ind + "// Must come after ShowWindow: while the window is hidden the call",
    ind + "// succeeds but the affinity stays WDA_NONE and the frame is recorded.",
    ind + "if !capturable {",
    ind + "    let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);",
    ind + "}",
]
lines[a:b+1] = new
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("show block rewritten; replaced", b - a + 1, "lines")
