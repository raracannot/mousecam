import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\recorder.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
i = next(k for k, l in enumerate(lines) if l.strip() == "let mut dropped = 0u32;")
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines[i:i] = [ind + "let mut write_err: Option<String> = None;"]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("write_err declared at line", i+1)
