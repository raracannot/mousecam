import io
p = r"rust\mc-engine\src\recorder.rs"
s = io.open(p, encoding="utf-8").read()
old = '        std::fs::create_dir_all(&out_dir).map_err(|e| format!("创建目录失败: {e}"))?;'
new = '        std::fs::create_dir_all(&out_dir)\n            .map_err(|e| format!("创建目录失败 {}: {e}", out_dir.display()))?;'
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("path added to the error")
