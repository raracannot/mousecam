import io

# --- 1. generation counter so an old supervisor cannot outlive its start() ---
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

rep("static STARTED: AtomicBool", "static GEN: AtomicU64 = AtomicU64::new(0);\n\nstatic STARTED: AtomicBool")
rep("""            .spawn(|| {
                if std::env::var_os("MC_HUD_INPROC").is_some() {
                    unsafe { run() }
                } else {
                    run_remote();
                    STARTED.store(false, Ordering::SeqCst);
                }
            })""",
"""            .spawn(|| {
                if std::env::var_os("MC_HUD_INPROC").is_some() {
                    unsafe { run() }
                } else {
                    // A supervisor belongs to the start() that created it: stop()
                    // bumps the generation, so a supervisor that has not noticed
                    // yet cannot keep a second overlay process alive.
                    let me = GEN.fetch_add(1, Ordering::SeqCst) + 1;
                    run_remote(me);
                    if GEN.load(Ordering::SeqCst) == me {
                        STARTED.store(false, Ordering::SeqCst);
                    }
                }
            })""")
rep("fn run_remote() {", "fn run_remote(me: u64) {")
rep("    while STARTED.load(Ordering::SeqCst) {", "    while STARTED.load(Ordering::SeqCst) && GEN.load(Ordering::SeqCst) == me {")
rep("""pub fn stop() {
    STARTED.store(false, Ordering::SeqCst);""",
"""pub fn stop() {
    GEN.fetch_add(1, Ordering::SeqCst);
    STARTED.store(false, Ordering::SeqCst);""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("supervisor generation added")

# --- 2. one overlay process only, whatever spawns it ---
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()
old = """pub fn main() -> i32 {"""
new = """/// Only one overlay may exist at a time. Two of them draw two different frames
/// and the result looks like the HUD disagreeing with the real crop, which is
/// far harder to diagnose than a process that simply refuses to start.
fn already_running() -> bool {
    use windows::Win32::Foundation::{GetLastError, ERROR_ALREADY_EXISTS};
    use windows::Win32::System::Threading::CreateMutexW;
    unsafe {
        let _ = CreateMutexW(None, true, w!("Local\\\\MouseCamOverlay"));
        GetLastError() == ERROR_ALREADY_EXISTS
    }
}

pub fn main() -> i32 {
    if already_running() {
        return 0;
    }"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("overlay singleton added")
