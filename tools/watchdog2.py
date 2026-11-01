import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# replace the run_on_main_thread watchdog: that call blocks when the main thread
# is stuck, so the watchdog hung with it and never reported anything.
start = s.index("/// Pings the UI thread and reports how long it takes to answer.")
end = s.index("/// Everything a bug report needs to be useful")
s = s[:start] + '''static LAST_BEAT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
static BOOT: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();

fn since_boot_ms() -> u64 {
    BOOT.get_or_init(std::time::Instant::now).elapsed().as_millis() as u64
}

/// Called from the webview every couple of seconds. Its timers only run while
/// the UI thread is alive, which is what makes this a usable liveness signal.
#[tauri::command]
fn heartbeat() {
    LAST_BEAT.store(since_boot_ms(), std::sync::atomic::Ordering::Relaxed);
}

/// Watches the heartbeat instead of posting work to the UI thread: the previous
/// version called run_on_main_thread, which blocks while the main thread is
/// stuck, so the watchdog stalled with the thing it was watching.
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
                    continue; // the page has not started beating yet
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

''' + s[end:]

# call it without the app handle
rep("""                    log_context();
                    start_stall_watchdog(app.handle().clone());""",
"""                    log_context();
                    start_stall_watchdog();""")

# register the command
rep("            log_event,", "            log_event,\n            heartbeat,")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("heartbeat watchdog installed")
