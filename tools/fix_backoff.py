import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:80]))
    s = s.replace(old, new)

# backoff state
rep("""    let mut child: Option<Child> = None;
    let mut stdin: Option<ChildStdin> = None;
    let mut last = String::new();""",
"""    let mut child: Option<Child> = None;
    let mut stdin: Option<ChildStdin> = None;
    let mut last = String::new();
    // A child that dies immediately would otherwise be respawned every 33 ms,
    // which turns one configuration problem into a process storm.
    let mut backoff_ms: u64 = 0;
    let mut spawned_at = std::time::Instant::now();""")

# wait out the backoff before respawning
rep("""        if stdin.is_none() {
            let spawned = Command::new(&exe)""",
"""        if stdin.is_none() {
            if backoff_ms > 0 {
                let deadline = std::time::Instant::now() + std::time::Duration::from_millis(backoff_ms);
                while std::time::Instant::now() < deadline {
                    if !STARTED.load(Ordering::SeqCst) || GEN.load(Ordering::SeqCst) != me {
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(50));
                }
            }
            let spawned = Command::new(&exe)""")

rep("""                Ok(mut c) => {
                    stdin = c.stdin.take();
                    child = Some(c);
                    last.clear();
                    crate::mc_info!("hud", "overlay process started");
                }""",
"""                Ok(mut c) => {
                    stdin = c.stdin.take();
                    child = Some(c);
                    last.clear();
                    spawned_at = std::time::Instant::now();
                    crate::mc_info!("hud", "overlay process started");
                }""")

# grow the backoff when the child dies young
rep("""            if let Ok(Some(_)) = c.try_wait() {
                crate::mc_warn!("hud", "overlay process exited - will restart");
                stdin = None;
                child = None;
            }""",
"""            if let Ok(Some(_)) = c.try_wait() {
                let lived = spawned_at.elapsed();
                backoff_ms = if lived < std::time::Duration::from_secs(2) {
                    (backoff_ms.max(100) * 2).min(5000)
                } else {
                    0
                };
                crate::mc_warn!(
                    "hud",
                    "overlay process exited after {} ms - restarting in {} ms",
                    lived.as_millis(),
                    backoff_ms
                );
                stdin = None;
                child = None;
            }""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("hud backoff installed")
