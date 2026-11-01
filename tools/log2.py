import io

def patch(path, pairs, enc="utf-8"):
    s = io.open(path, encoding=enc).read()
    for old, new in pairs:
        c = s.count(old)
        if c != 1:
            raise SystemExit("%s: matched %d for:\n%s" % (path, c, old[:160]))
        s = s.replace(old, new)
    io.open(path, "w", encoding=enc, newline="").write(s)
    print("patched", path)

main_py = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"

patch(main_py, [
# the old ad-hoc logger delegates to the shared one
("""fn log(msg: &str) {
    eprintln!("[mousecam] {msg}");
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            use std::io::Write;
            if let Ok(mut f) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(dir.join("mousecam.log"))
            {
                let _ = writeln!(f, "{msg}");
            }
        }
    }
}""",
"""fn log(msg: &str) {
    mc_engine::mc_info!("app", "{}", msg);
}"""),

# start the log before anything else can fail
("""    tauri::Builder::default()
        .setup(|app| {
            log_dpi_awareness();""",
"""    // Open the log before anything else: from here on every failure, including
    // a panic on a worker thread, ends up in the file.
    let log_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("mousecam.log")))
        .unwrap_or_else(|| PathBuf::from("mousecam.log"));
    let verbose = mc_api::settings().verbose || std::env::var("MC_VERBOSE").is_ok();
    mc_engine::log::init(log_path, verbose);
    mc_engine::log::install_panic_hook();

    tauri::Builder::default()
        .setup(|app| {
            log_dpi_awareness();"""),

# richer startup context: what makes a bug report actionable
("""            match builder.build() {
                Ok(_) => log("window created"),
                Err(e) => log(&format!("window creation failed: {e:?}")),
            }
            Ok(())""",
"""            match builder.build() {
                Ok(_) => {
                    log("window created");
                    log_context(app);
                }
                Err(e) => mc_engine::mc_error!("app", "window creation failed: {e:?}"),
            }
            Ok(())"""),
])

# startup context helper + the frontend logging command
s = io.open(main_py, encoding="utf-8").read()
anchor = "fn main() {"
helper = '''/// Everything a bug report needs to be useful, written once at startup.
fn log_context(app: &tauri::AppHandle) {
    use tauri::Manager;
    let _ = app;
    let ver = env!("CARGO_PKG_VERSION");
    mc_engine::mc_info!("app", "MouseCam {} ({} build)", ver, if cfg!(debug_assertions) { "debug" } else { "release" });
    mc_engine::mc_info!("app", "exe: {}", std::env::current_exe().map(|p| p.display().to_string()).unwrap_or_default());
    mc_engine::mc_info!("app", "log: {}", mc_engine::log::show(mc_engine::log::path()));
    mc_engine::mc_info!("app", "captures: {}", mc_engine::log::show(mc_api::captures_root()));
    mc_engine::mc_info!("app", "os: {}", std::env::consts::OS);
    for m in mc_api::list_monitors() {
        mc_engine::mc_info!(
            "app",
            "monitor {}: {}x{} at {},{} primary={} scale~{:.2}",
            m.index, m.w, m.h, m.x, m.y, m.primary, m.scale
        );
    }
    match mc_api::find_ffmpeg_path() {
        Some(p) => mc_engine::mc_info!("app", "ffmpeg: {}", mc_engine::log::show(p)),
        None => mc_engine::mc_warn!("app", "ffmpeg not found"),
    }
}

fn main() {'''
assert s.count(anchor) == 1
s = s.replace(anchor, helper)

# command so the frontend can report its own errors
cmd = '''#[tauri::command]
fn log_event(level: String, msg: String) {
    mc_engine::log::log(mc_engine::log::Level::parse(&level), "ui", &msg);
}

#[tauri::command]
fn log_verbose(on: bool) {
    mc_engine::log::set_verbose(on);
    mc_engine::mc_info!("app", "verbose logging {}", if on { "on" } else { "off" });
}

fn log(msg: &str) {'''
assert s.count("fn log(msg: &str) {") == 1
s = s.replace("fn log(msg: &str) {", cmd)

# register them
s = s.replace("            hotkey_status,", "            hotkey_status,\n            log_event,\n            log_verbose,")
io.open(main_py, "w", encoding="utf-8", newline="").write(s)
print("main.rs wired")
