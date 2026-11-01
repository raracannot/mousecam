import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
i = next(i for i, l in enumerate(lines) if "last_start().lock().unwrap() = (edit.clone(), monitor, hw);" in l and "preview_start" in "\n".join(lines[max(0, i-12):i]))
lines[i] = lines[i].replace(", hw);", ", None);")
print("preview_start site restored to None at line", i + 1)
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
