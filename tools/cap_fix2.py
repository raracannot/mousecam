import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\capture.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
i = next(k for k, l in enumerate(lines) if "lost: false," in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
if "resized" not in lines[i+1]:
    lines[i+1:i+1] = [
        ind + "resized: false,",
        ind + "unsupported_format: None,",
    ]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("initializer completed")
