import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()

start = s.index("pub fn captures_root() -> PathBuf {")
end = s.index("fn default_captures_dir() -> PathBuf {")
new = '''pub fn captures_root() -> PathBuf {
    let mut g = captures_root_cache().lock().unwrap();
    if let Some(p) = g.as_ref() {
        return p.clone();
    }
    let resolved = resolve_captures_root();
    *g = Some(resolved.clone());
    resolved
}

static CAPTURES_ROOT: std::sync::OnceLock<std::sync::Mutex<Option<PathBuf>>> = std::sync::OnceLock::new();

fn captures_root_cache() -> &'static std::sync::Mutex<Option<PathBuf>> {
    CAPTURES_ROOT.get_or_init(|| std::sync::Mutex::new(None))
}

fn invalidate_captures_root() {
    if let Some(m) = CAPTURES_ROOT.get() {
        *m.lock().unwrap() = None;
    }
}

/// Picks the first folder that can actually hold a recording.
///
/// The configured path is only a preference: on a machine where security software
/// blocks an unsigned executable from creating folders outside its own, every
/// write under the user profile fails with "access denied" and the recorder would
/// otherwise refuse to start with no way forward.
fn resolve_captures_root() -> PathBuf {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Some(dir) = settings().captures_dir.filter(|d| !d.trim().is_empty()) {
        candidates.push(PathBuf::from(dir));
    }
    candidates.push(default_captures_dir());
    candidates.push(local_app_dir().join("captures"));
    candidates.push(std::env::temp_dir().join("MouseCam").join("captures"));
    if let Ok(exe) = std::env::current_exe() {
        if let Some(d) = exe.parent() {
            candidates.push(d.join("captures"));
        }
    }

    let first = candidates.first().cloned();
    for c in &candidates {
        if std::fs::create_dir_all(c).is_ok() && writable(c) {
            if Some(c) != first.as_ref() {
                mc_engine::mc_warn!(
                    "captures",
                    "{} is not writable, using {} instead",
                    first.map(|p| p.display().to_string()).unwrap_or_default(),
                    c.display()
                );
            }
            return c.clone();
        }
    }
    mc_engine::mc_error!("captures", "no writable capture folder among {} candidates", candidates.len());
    candidates
        .into_iter()
        .next()
        .unwrap_or_else(|| PathBuf::from("captures"))
}

'''
s = s[:start] + new + s[end:]

# a settings change must re-resolve
s = s.replace("pub fn set_settings(", "pub fn set_settings(", 1)
old_set = """    let _ = std::fs::write(&path, txt);"""
if old_set in s:
    s = s.replace(old_set, """    let _ = std::fs::write(&path, txt);
    invalidate_captures_root();""", 1)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("captures root now falls back through candidates")
