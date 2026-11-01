import io
p = r"rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
old = '''/// The user's Videos library via `SHGetKnownFolderPath`.
fn videos_dir() -> Option<PathBuf> {
    use windows::Win32::System::Com::CoTaskMemFree;
    use windows::Win32::UI::Shell::{
        FOLDERID_Videos, SHGetKnownFolderPath, KF_FLAG_DEFAULT,
    };
    unsafe {
        let p = SHGetKnownFolderPath(&FOLDERID_Videos, KF_FLAG_DEFAULT, None).ok()?;
        let s = p.to_string().ok();
        CoTaskMemFree(Some(p.0 as *const _));
        let s = s?;
        if s.is_empty() {
            return None;
        }
        let path = PathBuf::from(s);
        std::fs::create_dir_all(&path).ok()?;
        Some(path)
    }
}

'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, "")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("duplicate removed")
