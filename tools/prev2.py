import io

# Tauri wrapper
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
if "preview_frame_path" not in s:
    old = """#[tauri::command]
async fn preview_frame() -> Result<String, String> {"""
    new = """#[tauri::command]
async fn preview_frame_path() -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(mc_api::preview_frame_path)
        .await
        .map_err(|e| format!("preview_frame_path thread: {e}"))?
}

#[tauri::command]
async fn preview_frame() -> Result<String, String> {"""
    assert s.count(old) == 1
    s = s.replace(old, new)
    s = s.replace("            preview_frame,", "            preview_frame,\n            preview_frame_path,")
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("command registered")

# front-end: load the file instead of a data URL
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
import re
m = re.search(r"async function tickRecPreview\(\)[\s\S]{0,1400}", s)
print("--- current tickRecPreview ---")
print(m.group(0)[:1000] if m else "not found")
