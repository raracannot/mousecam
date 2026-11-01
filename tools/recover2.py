import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = """/// Everything a bug report needs to be useful, written once at startup.
fn log_context() {"""
new = """/// Adopts recordings that a crash or a forced close left without a meta.json.
/// Runs off the main thread because it may call ffmpeg to learn a duration.
fn recover_orphans() {
    let n = mc_api::recover_orphan_clips();
    if n > 0 {
        mc_engine::mc_warn!("app", "recovered {n} interrupted recording(s)");
    }
}

/// Everything a bug report needs to be useful, written once at startup.
fn log_context() {"""
assert s.count(old) == 1
s = s.replace(old, new)

# call it right after the context log
old2 = """        log_context();"""
if s.count(old2) == 1:
    s = s.replace(old2, """        log_context();
        std::thread::spawn(recover_orphans);""")
else:
    raise SystemExit("log_context() call not found exactly once: %d" % s.count(old2))
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("recovery wired into startup")
