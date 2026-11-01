import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
old = """    let dir = std::env::temp_dir().join("MouseCam");
    let _ = std::fs::create_dir_all(&dir);"""
new = """    // Under the captures root: that folder is known to be writable (recordings
    // go there) and it is already inside the asset protocol scope. %TEMP% is
    // not guaranteed to exist as a usable directory.
    let dir = captures_root().join(".preview");
    std::fs::create_dir_all(&dir).map_err(|e| format!("创建预览目录失败: {e}"))?;"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("preview files go under the captures root")
