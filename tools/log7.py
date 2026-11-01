import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
if "debug_panic" not in s:
    s = s.replace("""#[tauri::command]
fn log_event(level: String, msg: String) {""",
"""/// Self-test for the logging system: panics on a worker thread so the panic
/// hook can be checked without crashing the UI thread.
#[tauri::command]
async fn debug_panic() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(|| panic!("deliberate test panic"))
        .await
        .map_err(|e| format!("{e}"))?;
    Ok(())
}

#[tauri::command]
fn log_event(level: String, msg: String) {""")
    s = s.replace("            log_event,", "            log_event,\n            debug_panic,")
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("debug_panic added")
