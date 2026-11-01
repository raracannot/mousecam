import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()

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
    shell_open(&p)
}

/// Asks the running shell to open a folder.
///
/// Spawning `explorer.exe` ourselves put a second copy of the shell on screen and
/// on some systems that copy fails to initialise (0xc0000142, "the application
/// was unable to start correctly"). `ShellExecute` hands the request to the shell
/// that is already running.
fn shell_open(p: &std::path::Path) -> Result<(), String> {
    use windows::core::HSTRING;
    use windows::Win32::UI::Shell::ShellExecuteW;
    use windows::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;
    unsafe {
        let op = HSTRING::from("open");
        let file = HSTRING::from(p.as_os_str().to_string_lossy().to_string());
        let r = ShellExecuteW(None, &op, &file, None, None, SW_SHOWNORMAL);
        // an HINSTANCE of 32 or below is an error code, not a handle
        if r.0 as isize <= 32 {
            return Err(format!("无法打开文件夹 (code {})", r.0 as isize));
        }
    }
    Ok(())
}

/// Opens the folder that holds the file. The shell cannot be asked to select a
/// file without COM plumbing, and opening the folder is what makes the log easy
/// to find.
pub fn reveal_file(path: String) -> Result<(), String> {
    let p = std::path::PathBuf::from(path.trim());
    if !p.exists() {
        return Err(format!("文件不存在: {}", p.display()));
    }
    match p.parent() {
        Some(dir) => shell_open(dir),
        None => shell_open(&p),
    }
}

'''
s = s[:start] + new + s[end:]
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("open via ShellExecute, no explorer spawn")
