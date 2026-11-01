import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
lines = io.open(p, encoding="utf-8").read().split("\n")

# 1) cut the block that ended up inside the loop-toggle handler
start = next(i for i, l in enumerate(lines) if "loadAppSettings().then((a) => {" in l)
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "});")
print("removing", start + 1, "..", end + 1)
block = lines[start:end+1]
del lines[start:end+1]

# 2) drop it at module level, at the end of the boot section
anchor = next(i for i, l in enumerate(lines) if "/* boot" in l.lower()) if any("/* boot" in l.lower() for l in lines) else None
if anchor is None:
    # append at the end, after everything is defined
    tail = len(lines)
    while tail > 0 and lines[tail-1].strip() == "":
        tail -= 1
    lines[tail:tail] = ["", "/* ---- boot: load the saved settings before the first paint ---- */"] + block
else:
    lines[anchor:anchor] = block
print("boot block placed at module level")

io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
