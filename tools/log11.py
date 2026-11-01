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

# verbose by default in a debug build
patch(r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs", [
("""        hw_encode: true,
        hud_default: true,
        verbose: false,
    };""",
"""        hw_encode: true,
        hud_default: true,
        // A debug build exists to be diagnosed, so log everything by default.
        verbose: cfg!(debug_assertions),
    };"""),
])

# stall watchdog: the only way to put "it hung" into the log with numbers
patch(r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs", [
("""/// Everything a bug report needs to be useful, written once at startup.""",
"""/// Pings the UI thread and reports how long it takes to answer. Without this a
/// freeze leaves no trace at all: the process keeps running, the log just stops.
fn start_stall_watchdog(app: tauri::AppHandle) {
    use std::sync::mpsc;
    use std::time::{Duration, Instant};
    std::thread::Builder::new()
        .name("watchdog".into())
        .spawn(move || loop {
            let t0 = Instant::now();
            let (tx, rx) = mpsc::channel();
            if app.run_on_main_thread(move || {
                let _ = tx.send(Instant::now());
            }).is_ok() {
                match rx.recv_timeout(Duration::from_millis(2000)) {
                    Ok(t1) => {
                        let lag = t1.duration_since(t0);
                        if lag > Duration::from_millis(400) {
                            mc_engine::mc_warn!(
                                "watch",
                                "main thread busy {} ms",
                                lag.as_millis()
                            );
                        }
                    }
                    Err(_) => mc_engine::mc_error!(
                        "watch",
                        "main thread STALLED for more than 2s"
                    ),
                }
            }
            std::thread::sleep(Duration::from_millis(500));
        })
        .ok();
}

/// Everything a bug report needs to be useful, written once at startup."""),
("""                    log("window created");
                    log_context();""",
"""                    log("window created");
                    log_context();
                    start_stall_watchdog(app.handle().clone());"""),
])
