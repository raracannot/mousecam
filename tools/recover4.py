import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

start = next(i for i, l in enumerate(lines) if l.strip() == ".spawn(log_context)")
end = next(i for i in range(start, len(lines)) if lines[i].strip() == ".ok();" and i > start)
ind = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
block = [
    ind + ".spawn(log_context)",
    ind + ".ok();",
    ind + "std::thread::Builder::new()",
    ind + "    .name(\"recover\".into())",
    ind + "    .spawn(recover_orphans)",
    ind + "    .ok();",
]
lines[start:end+1] = block
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("chain repaired")
