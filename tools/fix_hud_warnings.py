import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# 1) WM_ERASEBKGND was not imported, so the arm was a catch-all binding that
#    swallowed every message (the compiler warned "unused variable").
i = next(i for i, l in enumerate(lines) if "WM_DESTROY, WM_PAINT," in l)
lines[i] = lines[i].replace("WM_DESTROY, WM_PAINT,", "WM_DESTROY, WM_ERASEBKGND, WM_PAINT,")
print("import fixed:", lines[i].strip())

# 2) dead `resized`
j = next(j for j, l in enumerate(lines) if "let resized = last_geom.map(" in l)
del lines[j]
print("removed dead resized")

# 3) MC_HUD_CAPTURABLE must still be honoured: it exists so the HUD can be
#    screenshotted while developing.
k = next(k for k, l in enumerate(lines) if "let mut affinity = capturable;" in l)
ind = lines[k][:len(lines[k]) - len(lines[k].lstrip())]
lines[k] = ind + "// MC_HUD_CAPTURABLE=1 keeps the frame capturable for screenshots."
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("affinity placeholder replaced")

s = io.open(p, encoding="utf-8").read()
old = """    if !shown {
        let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);
        shown = true;
        // Must come after ShowWindow: while the window is hidden the call
        // succeeds but the affinity stays WDA_NONE and the frame is recorded.
        let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);
    } else {
        // retried until it sticks (a display change can clear it)
        let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);
    }"""
new = """    if !shown {
        let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);
        shown = true;
    }
    // Must come after ShowWindow: while the window is hidden the call succeeds
    // but the affinity stays WDA_NONE and the frame ends up in the recording.
    if !capturable {
        let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);
    }"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("capturable honoured again")
