import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = """#[tauri::command]
fn heartbeat() {
    LAST_BEAT.store(since_boot_ms(), std::sync::atomic::Ordering::Relaxed);
}"""
new = """#[tauri::command]
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
}"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("heartbeat logs its own state")
