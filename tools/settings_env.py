import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
old = """fn settings_file() -> PathBuf {
    local_app_dir().join("settings.ini")
}"""
new = """fn settings_file() -> PathBuf {
    // MC_SETTINGS lets a portable copy keep its settings next to the binary
    // (and lets the test harness point it at a writable folder).
    if let Ok(p) = std::env::var("MC_SETTINGS") {
        if !p.trim().is_empty() {
            return PathBuf::from(p);
        }
    }
    local_app_dir().join("settings.ini")
}"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("MC_SETTINGS honoured")
