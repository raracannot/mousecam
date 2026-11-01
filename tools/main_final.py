import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("main.rs: matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# 1) an installed copy lives in Program Files, where the log next to the exe
#    cannot be created - fall back to the per-user data dir instead of silently
#    logging nowhere.
rep("""    let verbose = mc_api::settings().verbose || std::env::var("MC_VERBOSE").is_ok();
    mc_engine::log::init(log_path, verbose);""",
"""    let verbose = mc_api::settings().verbose
        || std::env::var("MC_VERBOSE").map(|v| v != "0" && v != "false").unwrap_or(false);
    if !mc_engine::log::init(log_path, verbose) {
        let fallback = std::env::var("LOCALAPPDATA")
            .map(|d| PathBuf::from(d).join("MouseCam").join("mousecam.log"))
            .unwrap_or_else(|_| PathBuf::from("mousecam.log"));
        let _ = std::fs::create_dir_all(fallback.parent().unwrap_or(&fallback));
        let _ = mc_engine::log::init(fallback, verbose);
    }""")

# 2) app_settings must be able to fail: unwrap_or_default() handed the dialog
#    ("", "", false, false, false), which it then saved back over real settings.
rep("""async fn app_settings() -> (String, String, bool, bool, bool) {
    tauri::async_runtime::spawn_blocking(mc_api::app_settings)
        .await
        .unwrap_or_default()
}""",
"""async fn app_settings() -> Result<(String, String, bool, bool, bool), String> {
    tauri::async_runtime::spawn_blocking(mc_api::app_settings)
        .await
        .map_err(|e| format!("app_settings thread: {e}"))
}""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("main.rs updated")

# 3) log_context does PATH walks and a write probe on the main thread during
#    setup; move it to a worker so startup is never blocked by a slow share.
s = io.open(p, encoding="utf-8").read()
old = "                    log_context();"
new = """                    std::thread::Builder::new()
                        .name("ctx".into())
                        .spawn(log_context)
                        .ok();"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("startup context moved off the main thread")
