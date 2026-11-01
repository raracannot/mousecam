import io

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()

start = s.index("#[tauri::command]")
end = s.index("fn log(msg: &str) {")
old = s[start:end]

new = '''// NOTE: every command that can take more than a moment is `async` and runs on
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
async fn app_settings() -> (String, String, bool, bool) {
    tauri::async_runtime::spawn_blocking(mc_api::app_settings)
        .await
        .unwrap_or_default()
}

#[tauri::command]
async fn set_app_settings(captures_dir: String, hw: bool, hud: bool) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || mc_api::set_app_settings(captures_dir, hw, hud))
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

'''
s = s[:start] + new + s[end:]

# register the new settings commands
old_reg = """            hotkey_status,"""
if old_reg in s and "app_settings," not in s:
    s = s.replace(old_reg, """            hotkey_status,
            app_settings,
            set_app_settings,
            open_folder,""")

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("commands made async")
