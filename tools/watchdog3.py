import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# replace the blocking watchdog definition (lines ~294..333, up to log_context doc)
start = next(i for i, l in enumerate(lines) if "Pings the UI thread" in l)
end = next(i for i, l in enumerate(lines) if "Everything a bug report needs" in l)
new = '''static LAST_BEAT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static BOOT: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();

fn since_boot_ms() -> u64 {
    BOOT.get_or_init(std::time::Instant::now).elapsed().as_millis() as u64
}

/// Called from the webview every couple of seconds. Webview timers only run
/// while the UI thread is alive, which is what makes this a liveness signal.
#[tauri::command]
fn heartbeat() {
    LAST_BEAT.store(since_boot_ms(), std::sync::atomic::Ordering::Relaxed);
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

'''.split("\n")
lines[start:end] = new

src = "\n".join(lines)
src = src.replace("start_stall_watchdog(app.handle().clone());", "start_stall_watchdog();")
src = src.replace("            log_event,", "            log_event,\n            heartbeat,")
io.open(p, "w", encoding="utf-8", newline="").write(src)
print("watchdog replaced with a heartbeat version")
