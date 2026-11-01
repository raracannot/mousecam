import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

i = next(i for i, l in enumerate(lines) if "did_move = true;" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]

# Restore what an earlier edit of this block removed: show the window on the
# first placement, and only then ask the compositor to keep it out of captures
# (the call silently does nothing while the window is still hidden).
restored = [
    ind + "if !shown {",
    ind + "    let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);",
    ind + "    shown = true;",
    ind + "    // Must come after ShowWindow: while the window is hidden the call",
    ind + "    // succeeds but the affinity stays WDA_NONE and the frame is recorded.",
    ind + "    let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);",
    ind + "} else {",
    ind + "    // retried until it sticks (a display change can clear it)",
    ind + "    let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);",
    ind + "}",
]
lines[i+1:i+1] = restored
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("show restored")
