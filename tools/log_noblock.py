import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\log.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for: %s" % (c, old[:120]))
    s = s.replace(old, new)

# A panic inside log() would hold the sink mutex; the hook then locking it again
# would deadlock the thread that is trying to report the panic.
rep("""        let thread = std::thread::current();
        log(
            Level::Error,
            "panic",
            &format!(
                "{} at {} (thread {})",
                payload,
                loc,
                thread.name().unwrap_or("unnamed")
            ),
        );
        default(info);""",
"""        let thread = std::thread::current();
        log_no_block(
            Level::Error,
            "panic",
            &format!(
                "{} at {} (thread {})",
                payload,
                loc,
                thread.name().unwrap_or("unnamed")
            ),
        );
        default(info);""")

rep("""fn truncate(s: &str, n: usize) -> String {""",
"""/// Same as `log`, but never waits for the sink. Used from the panic hook: if
/// the panic happened while another frame of this thread held that lock, a
/// blocking lock would hang the very thread that is trying to report it.
pub fn log_no_block(level: Level, target: &str, msg: &str) {
    let line = format!(
        "{}  {}  [{:<10}] {}\\n",
        stamp(),
        level.tag(),
        truncate(target, 10),
        msg
    );
    eprint!("{line}");
    if let Ok(mut s) = cell().try_lock() {
        if let Some(f) = s.file.as_mut() {
            let _ = f.write_all(line.as_bytes());
            let _ = f.flush();
        }
    }
}

fn truncate(s: &str, n: usize) -> String {""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("panic path made non-blocking")
