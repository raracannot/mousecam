import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

i = next(i for i, l in enumerate(lines) if 'mc_info!("record", "start: monitor=' in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
block = [
    ind + "// None means no explicit choice (the hotkey path): use the saved",
    ind + "// preference, but only when this machine can encode in hardware.",
    ind + "let hw = Some(hw.unwrap_or_else(|| settings().hw_encode && nvenc_available()));",
]
lines[i:i] = block

n = 0
for j, l in enumerate(lines):
    if "last_start().lock().unwrap() = (edit.clone(), monitor, None);" in l:
        lines[j] = l.replace(", None);", ", hw);")
        n += 1
print("last_start updated at", n, "sites")
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
