import io

# 1) explorer.exe instead of ShellExecuteW: its HINSTANCE return is an error
#    code below 32, which is what made every click fail silently.
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
start = s.index("pub fn open_folder(dir: String) -> Result<(), String> {")
end = s.index("fn clip_dto(", start)
new = '''pub fn open_folder(dir: String) -> Result<(), String> {
    let p = std::path::PathBuf::from(dir.trim());
    if p.as_os_str().is_empty() {
        return Err("没有可打开的文件夹".into());
    }
    std::fs::create_dir_all(&p).map_err(|e| format!("无法创建文件夹: {e}"))?;
    if !p.is_dir() {
        return Err(format!("不是文件夹: {}", p.display()));
    }
    // ShellExecuteW returns an HINSTANCE whose value is an error code when it is
    // 32 or below, which is easy to mistreat; explorer.exe is what actually opens
    // a folder window and it either starts or it does not.
    std::process::Command::new("explorer.exe")
        .arg(&p)
        .spawn()
        .map_err(|e| format!("无法打开文件夹: {e}"))?;
    Ok(())
}

/// Opens the folder and highlights the file, which is what makes a log easy to
/// find and attach to a bug report.
pub fn reveal_file(path: String) -> Result<(), String> {
    let p = std::path::PathBuf::from(path.trim());
    if !p.exists() {
        return Err(format!("文件不存在: {}", p.display()));
    }
    std::process::Command::new("explorer.exe")
        .arg(format!("/select,{}", p.display()))
        .spawn()
        .map_err(|e| format!("无法定位文件: {e}"))?;
    Ok(())
}

'''
s = s[:start] + new + s[end:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("open_folder now uses explorer.exe, reveal_file added")

# 2) open_log highlights the log file instead of just opening its folder
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = """async fn open_log() -> Result<(), String> {
    let p = mc_engine::log::path();
    let dir = p.parent().map(|d| d.display().to_string()).unwrap_or_default();
    tauri::async_runtime::spawn_blocking(move || mc_api::open_folder(dir))
        .await
        .map_err(|e| format!("open_log thread: {e}"))?
}"""
new = """async fn open_log() -> Result<(), String> {
    let p = mc_engine::log::path();
    let path = p.display().to_string();
    tauri::async_runtime::spawn_blocking(move || {
        // Select the file itself so it is obvious what to attach to a report.
        mc_api::reveal_file(path.clone())
            .or_else(|_| mc_api::open_folder(
                std::path::PathBuf::from(&path)
                    .parent()
                    .map(|d| d.display().to_string())
                    .unwrap_or_default(),
            ))
    })
    .await
    .map_err(|e| format!("open_log thread: {e}"))?
}"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("open_log reveals the file")

# 3) the toast must sit above the settings dialog (which is z-index 60)
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
old = """.toast {
  position: fixed;
  left: 50%;
  bottom: 26px;"""
new = """.toast {
  position: fixed;
  /* above the settings dialog (z-index 60): a message the user cannot see is
     indistinguishable from a button that does nothing */
  z-index: 200;
  left: 50%;
  bottom: 26px;"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("toast raised above the dialog")
