import io

# a query the window-close handler can ask
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
if "pub fn recording_active" not in s:
    anchor = "pub fn record_stop()"
    i = s.index(anchor)
    s = s[:i] + "/// True while a recording is running (used by the window-close guard).\npub fn recording_active() -> bool {\n    session().lock().unwrap().is_some()\n}\n\n" + s[i:]
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("recording_active added")

# finalise the take instead of losing it when the window closes
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = """        .run(tauri::generate_context!())"""
new = """        .on_window_event(|_window, event| {
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
        .run(tauri::generate_context!())"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("close guard wired")
