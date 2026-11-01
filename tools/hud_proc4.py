import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# start(): prefer the child process, keep the in-process thread one env var away
rep("""        std::thread::Builder::new()
            .name("mc-hud".into())
            .spawn(|| unsafe { run() })
            .ok();""",
"""        std::thread::Builder::new()
            .name("mc-hud".into())
            .spawn(|| {
                if std::env::var_os("MC_HUD_INPROC").is_some() {
                    unsafe { run() }
                } else {
                    run_remote();
                    STARTED.store(false, Ordering::SeqCst);
                }
            })
            .ok();""")

# the supervisor
rep("""pub fn stop() {""",
"""/// Feeds the overlay process. The child owns the window and a real message
/// loop; this side only writes a line when the state actually changes.
///
/// Isolation is the point: if the overlay dies the recording does not, and if
/// the parent dies the pipe closes and the child exits on EOF, so no orphan can
/// be left behind.
fn run_remote() {
    use std::io::Write;
    use std::process::{Child, ChildStdin, Command, Stdio};

    let exe = match std::env::current_exe() {
        Ok(p) => p,
        Err(_) => return,
    };
    let mut child: Option<Child> = None;
    let mut stdin: Option<ChildStdin> = None;
    let mut last = String::new();

    while STARTED.load(Ordering::SeqCst) {
        if stdin.is_none() {
            let spawned = Command::new(&exe)
                .arg("--hud")
                .stdin(Stdio::piped())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .creation_flags(0x0800_0000) // CREATE_NO_WINDOW
                .spawn();
            match spawned {
                Ok(mut c) => {
                    stdin = c.stdin.take();
                    child = Some(c);
                    last.clear();
                    crate::mc_info!("hud", "overlay process started");
                }
                Err(e) => crate::mc_warn!("hud", "cannot start the overlay process: {e}"),
            }
        }

        let (rect, enabled, label, cfg, mon) = {
            let g = state().lock().unwrap();
            (g.rect, g.enabled, g.label.clone(), g.cfg, g.monitor)
        };

        let mut buf = String::new();
        buf.push_str(&format!(
            "cfg {} {} {}\\n",
            cfg.thickness,
            cfg.show_label as i32,
            cfg.brackets as i32
        ));
        buf.push_str(&format!("label {}\\n", label));
        buf.push_str(if enabled { "show\\n" } else { "hide\\n" });
        if let (Some(r), Some(m)) = (rect, mon) {
            if r.w > 8 && r.h > 8 {
                buf.push_str(&format!(
                    "frame {} {} {} {} {} {} {} {}\\n",
                    r.x, r.y, r.w, r.h, m.x, m.y, m.w, m.h
                ));
            }
        }

        if buf != last {
            if let Some(si) = stdin.as_mut() {
                if si.write_all(buf.as_bytes()).is_err() || si.flush().is_err() {
                    crate::mc_warn!("hud", "overlay pipe closed - restarting it");
                    stdin = None;
                    child = None;
                    continue;
                }
            }
            last = buf;
        }

        // notice a dead child even while nothing is changing
        if let Some(c) = child.as_mut() {
            if let Ok(Some(_)) = c.try_wait() {
                crate::mc_warn!("hud", "overlay process exited - will restart");
                stdin = None;
                child = None;
            }
        }

        std::thread::sleep(std::time::Duration::from_millis(33));
    }

    drop(stdin);
    if let Some(mut c) = child {
        let _ = c.kill();
        let _ = c.wait();
    }
    crate::mc_info!("hud", "overlay process stopped");
}

pub fn stop() {""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("supervisor added")
