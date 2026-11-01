import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
old = """pub fn set_app_settings(
    captures_dir: String,
    hw: bool,
    hud: bool,
    verbose: bool,
) -> Result<(), String> {
    set_settings(captures_dir, hw, hud, verbose)"""
new = """pub fn set_app_settings(
    captures_dir: String,
    hw: bool,
    hud: bool,
    verbose: bool,
) -> Result<(), String> {
    // Saves used to succeed with an unusable folder, and the failure only showed
    // up later as "创建目录失败" when recording started. Refuse it here instead.
    let trimmed = captures_dir.trim();
    if !trimmed.is_empty() {
        let p = PathBuf::from(trimmed);
        std::fs::create_dir_all(&p).map_err(|e| format!("无法创建该文件夹: {e}"))?;
        if !writable(&p) {
            return Err(format!("该文件夹不可写: {}", p.display()));
        }
    }
    set_settings(captures_dir, hw, hud, verbose)"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("settings validated on save")
