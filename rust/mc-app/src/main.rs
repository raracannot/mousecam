#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! Tauri shell. All real work lives in `mc-api`, which the local HTTP demo
//! server uses too — the two transports expose the same six operations, so the
//! front-end never knows the difference.

use std::path::{Path, PathBuf};

// NOTE: every command that can take more than a moment is `async` and runs on
// a blocking pool. A sync command executes on the main thread, and blocking it
// (a JPEG encode for the live preview, a 270 ms still decode, starting the
// recorder) starves the window's message loop - Windows then shows the app as
// "not responding" even though nothing is actually deadlocked.
#[tauri::command]
async fn list_clips() -> Result<Vec<mc_api::ClipDto>, String> {
    tauri::async_runtime::spawn_blocking(mc_api::list_clips)
        .await
        .map_err(|e| format!("list_clips thread: {e}"))
}

#[tauri::command]
async fn open_clip(dir: String) -> Result<mc_api::ClipDto, String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::open_clip(dir))
        .await
        .map_err(|e| format!("open_clip thread: {e}"))?
}

#[tauri::command]
async fn api_bake(dir: String, edit: String) -> Result<mc_api::BakeDto, String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::api_bake(dir, edit))
        .await
        .map_err(|e| format!("bake thread: {e}"))?
}

#[tauri::command]
async fn track_points(dir: String) -> Result<Vec<Vec<f32>>, String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::track_points(dir))
        .await
        .map_err(|e| format!("track_points thread: {e}"))?
}

#[tauri::command]
async fn still(
    dir: String,
    edit: String,
    frame: i32,
    max_w: u32,
    kind: String,
) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::still(dir, edit, frame, max_w, kind))
        .await
        .map_err(|e| format!("still thread: {e}"))?
}

#[tauri::command]
async fn record_start(
    edit: String,
    monitor: Option<i32>,
    hw: Option<bool>,
) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::record_start(edit, monitor, hw))
        .await
        .map_err(|e| format!("record_start thread: {e}"))?
}

#[tauri::command]
async fn record_stop() -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(mc_api::record_stop)
        .await
        .map_err(|e| format!("record_stop thread: {e}"))?
}

#[tauri::command]
fn record_status() -> mc_api::RecStatus {
    mc_api::record_status()
}

#[tauri::command]
async fn render_proxy(dir: String, edit: String, height: u32) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::render_proxy(dir, edit, height))
        .await
        .map_err(|e| format!("render_proxy thread: {e}"))?
}

#[tauri::command]
async fn preview_start(edit: String, monitor: Option<i32>) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::preview_start(edit, monitor))
        .await
        .map_err(|e| format!("preview_start thread: {e}"))?
}

#[tauri::command]
fn hotkey_status() -> (bool, bool) {
    mc_api::hotkey_status()
}

#[tauri::command]
async fn nvenc_available() -> bool {
    tauri::async_runtime::spawn_blocking(mc_api::nvenc_available)
        .await
        .unwrap_or(false)
}

#[tauri::command]
async fn list_monitors() -> Vec<mc_api::MonitorDto> {
    tauri::async_runtime::spawn_blocking(mc_api::list_monitors)
        .await
        .unwrap_or_default()
}

#[tauri::command]
async fn preview_stop() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(mc_api::preview_stop)
        .await
        .map_err(|e| format!("preview_stop thread: {e}"))
}

#[tauri::command]
async fn preview_set_params(edit: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::preview_set_params(edit))
        .await
        .map_err(|e| format!("preview_set_params thread: {e}"))
}

#[tauri::command]
async fn preview_frame_path() -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(mc_api::preview_frame_path)
        .await
        .map_err(|e| format!("preview_frame_path thread: {e}"))?
}

#[tauri::command]
async fn preview_frame() -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(mc_api::preview_frame)
        .await
        .map_err(|e| format!("preview_frame thread: {e}"))?
}

#[tauri::command]
fn hud_set(enabled: bool) {
    mc_api::hud_set(enabled);
}

#[tauri::command]
fn hud_set_config(thickness: i32, label: bool, brackets: bool) {
    mc_api::hud_set_config(thickness, label, brackets);
}

#[tauri::command]
fn hud_get_config() -> (i32, bool, bool) {
    mc_api::hud_get_config()
}

#[tauri::command]
fn hud_get() -> bool {
    mc_api::hud_get()
}

#[tauri::command]
async fn media_path(dir: String, which: String) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::media_path(dir, which))
        .await
        .map_err(|e| format!("media_path thread: {e}"))?
}

#[tauri::command]
async fn app_settings() -> Result<(String, String, bool, bool, bool), String> {
    tauri::async_runtime::spawn_blocking(mc_api::app_settings)
        .await
        .map_err(|e| format!("app_settings thread: {e}"))
}

#[tauri::command]
async fn set_app_settings(
    captures_dir: String,
    hw: bool,
    hud: bool,
    verbose: bool,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        mc_api::set_app_settings(captures_dir, hw, hud, verbose)
    })
        .await
        .map_err(|e| format!("set_app_settings thread: {e}"))?
}

#[tauri::command]
async fn open_folder(dir: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::open_folder(dir))
        .await
        .map_err(|e| format!("open_folder thread: {e}"))?
}

#[tauri::command]
async fn export(
    dir: String,
    edit: String,
    out: String,
    format: Option<String>,
    quality: Option<i32>,
    width: Option<i32>,
    fps: Option<i32>,
) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || {
        mc_api::export(dir, edit, out, format, quality, width, fps)
    })
    .await
    .map_err(|e| format!("export thread: {e}"))?
}

/// Self-test for the logging system: panics on a worker thread so the panic
/// hook can be checked without crashing the UI thread.
#[tauri::command]
async fn debug_panic() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(|| panic!("deliberate test panic"))
        .await
        .map_err(|e| format!("{e}"))?;
    Ok(())
}

#[tauri::command]
fn log_event(level: String, msg: String) {
    mc_engine::log::log(mc_engine::log::Level::parse(&level), "ui", &msg);
}

#[tauri::command]
async fn open_log() -> Result<(), String> {
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
}

#[tauri::command]
fn log_verbose(on: bool) {
    mc_engine::log::set_verbose(on);
    mc_engine::mc_info!("app", "verbose logging {}", if on { "on" } else { "off" });
}

fn log(msg: &str) {
    mc_engine::mc_info!("app", "{}", msg);
}

/// A directory can be created and still refuse writes (Controlled Folder
/// Access and similar policies), so probe with an actual file.
fn profile_is_usable(dir: &Path) -> bool {
    if std::fs::create_dir_all(dir).is_err() {
        return false;
    }
    let probe = dir.join(".write-probe");
    match std::fs::write(&probe, b"ok") {
        Ok(()) => {
            let _ = std::fs::remove_file(probe);
            true
        }
        Err(_) => false,
    }
}

/// Tauri always assigns `data_directory` itself (pointing at the app local data
/// dir), which overrides `WEBVIEW2_USER_DATA_FOLDER`. In locked-down setups
/// that directory is not writable, WebView2 fails during setup with
/// ERROR_ACCESS_DENIED and the app dies before any window exists. So we pick a
/// writable folder ourselves and hand it to the builder.
fn pick_profile_dir() -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    // 1) portable: next to the binary (always writable during development)
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join(".webview2"));
        }
    }
    // 2) the conventional location
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        candidates.push(Path::new(&local).join("MouseCam").join("WebView2"));
    }
    // 3) temp as a last resort
    if let Ok(temp) = std::env::var("TEMP") {
        candidates.push(Path::new(&temp).join("MouseCam-WebView2"));
    }

    for dir in candidates {
        if profile_is_usable(&dir) {
            return Some(dir);
        }
        log(&format!("profile not usable: {}", dir.display()));
    }
    None
}

/// 0 unaware, 1 system, 2 per-monitor. Logged because a mis-declared process
/// gets bitmap-stretched across displays with different scaling, which is what
/// makes WebView2 hang when the window is dragged to another monitor.
fn log_dpi_awareness() {
    use windows::Win32::UI::HiDpi::{GetAwarenessFromDpiAwarenessContext, GetThreadDpiAwarenessContext};
    unsafe {
        let ctx = GetThreadDpiAwarenessContext();
        let a = GetAwarenessFromDpiAwarenessContext(ctx);
        log(&format!("dpi awareness = {} ({:?})", a.0, a));
    }
}

static LAST_BEAT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static BOOT: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();

fn since_boot_ms() -> u64 {
    BOOT.get_or_init(std::time::Instant::now).elapsed().as_millis() as u64
}

/// Called from the webview every couple of seconds. Webview timers only run
/// while the UI thread is alive, which is what makes this a liveness signal.
#[tauri::command]
fn heartbeat() {
    let now = since_boot_ms();
    let prev = LAST_BEAT.swap(now, std::sync::atomic::Ordering::Relaxed);
    if prev == 0 {
        mc_engine::mc_info!("watch", "heartbeat established at {} ms", now);
    } else if now.saturating_sub(prev) > 2500 {
        // the UI thread was away long enough to be worth recording
        mc_engine::mc_warn!(
            "watch",
            "heartbeat resumed after a {} ms gap",
            now.saturating_sub(prev)
        );
    }
}

/// Watches the heartbeat rather than posting work to the UI thread. The previous
/// version used run_on_main_thread, which blocks while the main thread is stuck,
/// so the watchdog stalled together with the thing it was watching.
fn start_stall_watchdog() {
    std::thread::Builder::new()
        .name("watchdog".into())
        .spawn(|| {
            let mut last_report: u64 = 0;
            loop {
                std::thread::sleep(std::time::Duration::from_millis(500));
                let now = since_boot_ms();
                let beat = LAST_BEAT.load(std::sync::atomic::Ordering::Relaxed);
                if beat == 0 {
                    continue;
                }
                let silent = now.saturating_sub(beat);
                if silent > 4000 && now.saturating_sub(last_report) > 5000 {
                    last_report = now;
                    mc_engine::mc_error!(
                        "watch",
                        "UI thread STALLED - no heartbeat for {} ms",
                        silent
                    );
                }
            }
        })
        .ok();
}


/// Adopts recordings that a crash or a forced close left without a meta.json.
/// Runs off the main thread because it may call ffmpeg to learn a duration.
fn recover_orphans() {
    let n = mc_api::recover_orphan_clips();
    if n > 0 {
        mc_engine::mc_warn!("app", "recovered {n} interrupted recording(s)");
    }
}

/// Everything a bug report needs to be useful, written once at startup.
fn log_context() {
    let ver = env!("CARGO_PKG_VERSION");
    mc_engine::mc_info!("app", "MouseCam {} ({} build)", ver, if cfg!(debug_assertions) { "debug" } else { "release" });
    mc_engine::mc_info!("app", "exe: {}", std::env::current_exe().map(|p| p.display().to_string()).unwrap_or_default());
    mc_engine::mc_info!("app", "log: {}", mc_engine::log::show(mc_engine::log::path()));
    mc_engine::mc_info!("app", "captures: {}", mc_engine::log::show(mc_api::captures_root()));
    mc_engine::mc_info!("app", "os: {}", std::env::consts::OS);
    for m in mc_api::list_monitors() {
        mc_engine::mc_info!(
            "app",
            "monitor {}: {}x{} at {},{} primary={}",
            m.index, m.w, m.h, m.x, m.y, m.primary
        );
    }
    match mc_engine::clip::find_ffmpeg() {
        Some(p) => mc_engine::mc_info!("app", "ffmpeg: {}", mc_engine::log::show(p)),
        None => mc_engine::mc_warn!("app", "ffmpeg not found"),
    }
}

fn main() {
    // `--hud` runs only the overlay: no Tauri, no WebView2, no capture. It is
    // spawned by the main process and exits when its stdin closes, so it can
    // neither drag the UI down nor outlive the app.
    if std::env::args().any(|a| a == "--hud") {
        std::process::exit(mc_engine::hud_proc::main());
    }

    // One instance only: a second copy would fight over the screen duplication.
    if !mc_engine::single::claim_single_instance() {
        mc_engine::single::focus_existing_window();
        std::process::exit(0);
    }

    // NOTE: never call SetProcessDpiAwarenessContext here. Tauri sets the
    // per-monitor-v2 context during setup; a second call fails with
    // ERROR_ACCESS_DENIED and aborts startup.
    // Open the log before anything else: from here on every failure, including
    // a panic on a worker thread, ends up in the file.
    // MC_LOG lets a test run write its own file instead of overwriting the one a
    // user will want to send in after reproducing a bug.
    let log_path = match std::env::var("MC_LOG") {
        Ok(p) if !p.trim().is_empty() => PathBuf::from(p),
        _ => std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.join("mousecam.log")))
            .unwrap_or_else(|| PathBuf::from("mousecam.log")),
    };
    let verbose = mc_api::settings().verbose
        || std::env::var("MC_VERBOSE").map(|v| v != "0" && v != "false").unwrap_or(false);
    if !mc_engine::log::init(log_path, verbose) {
        let fallback = std::env::var("LOCALAPPDATA")
            .map(|d| PathBuf::from(d).join("MouseCam").join("mousecam.log"))
            .unwrap_or_else(|_| PathBuf::from("mousecam.log"));
        let _ = std::fs::create_dir_all(fallback.parent().unwrap_or(&fallback));
        let _ = mc_engine::log::init(fallback, verbose);
    }
    mc_engine::log::install_panic_hook();

    tauri::Builder::default()
        .setup(|app| {
            log_dpi_awareness();
        // global start/stop hotkeys (Ctrl+Alt+R or F9)
        mc_api::hotkeys_start();

            use tauri::WebviewWindowBuilder;

            let profile = pick_profile_dir();
            match &profile {
                Some(p) => log(&format!("webview2 profile: {}", p.display())),
                None => log("no writable webview2 profile found"),
            }

            let mut builder = WebviewWindowBuilder::new(app, "main", tauri::WebviewUrl::default())
                .title("MouseCam")
                .inner_size(1280.0, 860.0)
                .min_inner_size(960.0, 660.0)
                .decorations(false)
                .resizable(true)
                .center();

            if let Some(dir) = profile {
                builder = builder.data_directory(dir);
            }

            // Dev-only: expose a CDP port so the UI can be driven and
            // screenshotted over the DevTools protocol.
            if let Ok(args) = std::env::var("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS") {
                builder = builder.additional_browser_args(&args);
                log(&format!("browser args: {args}"));
            }

            match builder.build() {
                Ok(_) => {
                    log("window created");
                    std::thread::Builder::new()
                        .name("ctx".into())
                        .spawn(log_context)
                        .ok();
                        std::thread::Builder::new()
                            .name("recover".into())
                            .spawn(recover_orphans)
                            .ok();
                    start_stall_watchdog();
                }
                Err(e) => mc_engine::mc_error!("app", "window creation failed: {e:?}"),
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            list_clips,
            open_clip,
            api_bake,
            track_points,
            still,
            export,
            record_start,
            record_stop,
            record_status,
            render_proxy,
            media_path,
            preview_start,
            preview_stop,
            list_monitors,
            nvenc_available,
            hotkey_status,
            log_event,
            heartbeat,
            debug_panic,
            open_log,
            log_verbose,
            app_settings,
            set_app_settings,
            open_folder,
            preview_set_params,
            preview_frame,
            preview_frame_path,
            hud_set,
            hud_get,
            hud_set_config,
            hud_get_config
        ])
        .on_window_event(|_window, event| {
            // Closing mid-recording used to kill the process while ffmpeg still
            // held the file open, leaving an unplayable master with no meta.json:
            // the take existed on disk and was invisible in the library.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if mc_api::recording_active() {
                    mc_engine::mc_info!("app", "窗口关闭：先结束录制再退出");
                    match mc_api::record_stop() {
                        Ok(m) => mc_engine::mc_info!("app", "录制已收尾: {}", m),
                        Err(e) => mc_engine::mc_warn!("app", "收尾失败: {e}"),
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("MouseCam 启动失败");
}
