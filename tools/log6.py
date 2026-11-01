import io

# --- command to open the log folder
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
s = s.replace("""#[tauri::command]
fn log_verbose(on: bool) {""",
"""#[tauri::command]
async fn open_log() -> Result<(), String> {
    let p = mc_engine::log::path();
    let dir = p.parent().map(|d| d.display().to_string()).unwrap_or_default();
    tauri::async_runtime::spawn_blocking(move || mc_api::open_folder(dir))
        .await
        .map_err(|e| format!("open_log thread: {e}"))?
}

#[tauri::command]
fn log_verbose(on: bool) {""")
s = s.replace("            log_event,", "            log_event,\n            open_log,")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("open_log added")

# --- settings dialog: verbose switch + open-log button
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\index.html"
s = io.open(p, encoding="utf-8").read()
old = """        <label class="frow frow-check"><input type="checkbox" id="setHud" /> 录制时默认显示屏幕取景框</label>"""
new = """        <label class="frow frow-check"><input type="checkbox" id="setHud" /> 录制时默认显示屏幕取景框</label>
        <label class="frow frow-check"><input type="checkbox" id="setVerbose" /> 记录详细日志（排查问题时打开）</label>
        <div class="frow frow-actions">
          <button class="head-btn" id="setOpenLog">打开日志文件夹</button>
        </div>"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("settings UI updated")
