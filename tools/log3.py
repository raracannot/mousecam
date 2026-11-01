import io

# 1) mc-app needs the engine crate for the logger
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\Cargo.toml"
s = io.open(p, encoding="ascii").read()
if "mc-engine" not in s:
    s = s.replace('mc-api = { path = "../mc-api" }',
                  'mc-api = { path = "../mc-api" }\nmc-engine = { path = "../mc-engine" }')
    io.open(p, "w", encoding="ascii", newline="").write(s)
    print("mc-engine dependency added")

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for: %s" % (c, old[:140]))
    s = s.replace(old, new)

rep("    match mc_api::find_ffmpeg_path() {", "    match mc_engine::clip::find_ffmpeg() {")
rep("fn log_context(app: &tauri::AppHandle) {\n    use tauri::Manager;\n    let _ = app;\n",
    "fn log_context() {\n")
rep("                    log_context(app);", "                    log_context();")
rep("async fn app_settings() -> (String, String, bool, bool) {",
    "async fn app_settings() -> (String, String, bool, bool, bool) {")
rep("""async fn set_app_settings(captures_dir: String, hw: bool, hud: bool) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::set_app_settings(captures_dir, hw, hud))""",
"""async fn set_app_settings(
    captures_dir: String,
    hw: bool,
    hud: bool,
    verbose: bool,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        mc_api::set_app_settings(captures_dir, hw, hud, verbose)
    })""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("main.rs fixed")
