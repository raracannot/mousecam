import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# 1) the clear belongs at the END of run(), not in the loop's hidden branch -
#    there it made any hide (toggle off, crop unavailable) kill the thread for
#    good, so the HUD never came back when toggled on again.
i = next(i for i, l in enumerate(lines) if "STARTED.store(false, Ordering::SeqCst);" in l and i > 380)
del lines[i]
print("misplaced STARTED clear removed from the loop (line %d)" % (i + 1))

# put it after the loop instead
j = next(i for i, l in enumerate(lines) if "let _ = ShowWindow(hwnd, SW_HIDE);" in l and i > 380)
ind = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
lines[j:j] = [ind + "STARTED.store(false, Ordering::SeqCst);"]
print("STARTED cleared at thread exit instead")

# 2) the window class must be registered once, not once per start(): a restart
#    after a stop used to re-register and fail.
src = "\n".join(lines)
old = "    let _ = RegisterClassW(&class);"
if old in src:
    src = src.replace(old, """    // RegisterClassW fails if the class already exists, which is harmless on a
    // restart but must not be treated as an error.
    let _ = RegisterClassW(&class);""")
io.open(p, "w", encoding="utf-8", newline="").write(src)
print("class registration noted")
