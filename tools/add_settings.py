import io

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for:\n%s" % (c, old[:160]))
    s = s.replace(old, new)

# ---- settings storage replaces the hard-wired captures_root chain
old_root = s[s.index("pub fn captures_root() -> PathBuf {"):]
old_root = old_root[:old_root.index("\n}\n") + 3]

new_root = '''/// Where recordings are written. Order:
///   1. `MC_CAPTURES` (developer override)
///   2. the folder chosen in the settings dialog
///   3. the user's Videos library
///   4. `%LOCALAPPDATA%\\MouseCam\\captures` if the above is not writable
pub fn captures_root() -> PathBuf {
    if let Some(dir) = settings().captures_dir.filter(|d| !d.trim().is_empty()) {
        return PathBuf::from(dir);
    }
    let default = default_captures_dir();
    if std::fs::create_dir_all(&default).is_ok() && writable(&default) {
        return default;
    }
    let fallback = local_app_dir().join("captures");
    let _ = std::fs::create_dir_all(&fallback);
    fallback
}

fn default_captures_dir() -> PathBuf {
    if let Ok(d) = std::env::var("MC_CAPTURES") {
        if !d.trim().is_empty() {
            return PathBuf::from(d);
        }
    }
    match videos_dir() {
        Some(v) => v.join("MouseCam"),
        None => local_app_dir().join("captures"),
    }
}

fn writable(dir: &std::path::Path) -> bool {
    let probe = dir.join(".mc_write_test");
    match std::fs::write(&probe, b"x") {
        Ok(_) => {
            let _ = std::fs::remove_file(&probe);
            true
        }
        Err(_) => false,
    }
}

fn local_app_dir() -> PathBuf {
    for k in ["LOCALAPPDATA", "USERPROFILE"] {
        if let Ok(v) = std::env::var(k) {
            if !v.trim().is_empty() {
                return PathBuf::from(v).join("MouseCam");
            }
        }
    }
    PathBuf::from("MouseCam")
}

/// The user's Videos library via `SHGetKnownFolderPath`.
fn videos_dir() -> Option<PathBuf> {
    use windows::Win32::System::Com::CoTaskMemFree;
    use windows::Win32::UI::Shell::{FOLDERID_Videos, SHGetKnownFolderPath, KF_FLAG_DEFAULT};
    unsafe {
        let p = SHGetKnownFolderPath(&FOLDERID_Videos, KF_FLAG_DEFAULT, None).ok()?;
        let s = p.to_string().ok();
        CoTaskMemFree(Some(p.0 as *const _));
        let s = s?;
        if s.is_empty() {
            return None;
        }
        Some(PathBuf::from(s))
    }
}

// ---------------------------------------------------------------- settings
//
// Line based, like `.mcl`: `key=value`, `#` comments. No extra dependency and
// it stays readable if someone has to fix it by hand.

#[derive(Clone, Default)]
pub struct AppSettings {
    pub captures_dir: Option<String>,
    pub hw_encode: bool,
    pub hud_default: bool,
}

fn settings_file() -> PathBuf {
    local_app_dir().join("settings.ini")
}

pub fn settings() -> AppSettings {
    static CACHE: OnceLock<Mutex<Option<AppSettings>>> = OnceLock::new();
    let cell = CACHE.get_or_init(|| Mutex::new(None));
    let mut g = cell.lock().unwrap();
    if let Some(s) = g.as_ref() {
        return s.clone();
    }
    let mut out = AppSettings {
        captures_dir: None,
        hw_encode: true,
        hud_default: true,
    };
    if let Ok(txt) = std::fs::read_to_string(settings_file()) {
        for line in txt.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let Some((k, v)) = line.split_once('=') else {
                continue;
            };
            let v = v.trim();
            match k.trim() {
                "captures" if !v.is_empty() => out.captures_dir = Some(v.to_string()),
                "hw" => out.hw_encode = v == "1" || v.eq_ignore_ascii_case("true"),
                "hud" => out.hud_default = v == "1" || v.eq_ignore_ascii_case("true"),
                _ => {}
            }
        }
    }
    *g = Some(out.clone());
    out
}

pub fn set_settings(captures_dir: String, hw: bool, hud: bool) -> Result<(), String> {
    let dir = captures_dir.trim().to_string();
    let path = settings_file();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("创建配置目录失败: {e}"))?;
    }
    let body = format!(
        "# MouseCam 设置\\ncaptures={}\\nhw={}\\nhud={}\\n",
        dir,
        if hw { 1 } else { 0 },
        if hud { 1 } else { 0 }
    );
    std::fs::write(&path, body).map_err(|e| format!("写入配置失败: {e}"))?;
    if let Some(cell) = SETTINGS_CACHE.get() {
        *cell.lock().unwrap() = None;
    }
    Ok(())
}

static SETTINGS_CACHE: std::sync::OnceLock<Mutex<Option<AppSettings>>> = std::sync::OnceLock::new();

/// Opens a folder in Explorer.
pub fn open_folder(dir: String) -> Result<(), String> {
    use windows::core::HSTRING;
    use windows::Win32::UI::Shell::ShellExecuteW;
    use windows::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;
    let p = std::path::PathBuf::from(&dir);
    let _ = std::fs::create_dir_all(&p);
    unsafe {
        let op = HSTRING::from("open");
        let file = HSTRING::from(p.to_string_lossy().to_string());
        let r = ShellExecuteW(None, &op, &file, None, None, SW_SHOWNORMAL);
        if r.0 as isize <= 32 {
            return Err("无法打开文件夹".into());
        }
    }
    Ok(())
}
'''
s = s.replace(old_root, new_root)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("settings + captures_root rewritten")
