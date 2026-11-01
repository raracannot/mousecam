import io

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

def find(sub, start=0):
    for i in range(start, len(lines)):
        if sub in lines[i]:
            return i
    return -1

# generation counter
i = find("static STARTED: AtomicBool = AtomicBool::new(false);")
lines[i:i] = [
    "/// Bumped by every start()/stop(): a supervisor only owns the overlay while the",
    "/// generation it was created in is still current.",
    "static GEN: AtomicU64 = AtomicU64::new(0);",
    "",
]
s = "\n".join(lines)
s = s.replace("use std::sync::atomic::{AtomicBool, Ordering};",
              "use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};")

# start(): remember the generation, and do not clear STARTED from a stale run
old = """        .spawn(|| {
            if std::env::var_os("MC_HUD_INPROC").is_some() {
                unsafe { run() }
            } else {
                run_remote();
                STARTED.store(false, Ordering::SeqCst);
            }
        })"""
new = """        .spawn(|| {
            if std::env::var_os("MC_HUD_INPROC").is_some() {
                unsafe { run() }
            } else {
                let me = GEN.fetch_add(1, Ordering::SeqCst) + 1;
                run_remote(me);
                if GEN.load(Ordering::SeqCst) == me {
                    STARTED.store(false, Ordering::SeqCst);
                }
            }
        })"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)

s = s.replace("fn run_remote() {", "fn run_remote(me: u64) {")
s = s.replace("    while STARTED.load(Ordering::SeqCst) {\n        if stdin.is_none() {",
              "    while STARTED.load(Ordering::SeqCst) && GEN.load(Ordering::SeqCst) == me {\n        if stdin.is_none() {")
s = s.replace("""pub fn stop() {
    STARTED.store(false, Ordering::SeqCst);""",
"""pub fn stop() {
    // End the current generation first: a supervisor that has not noticed the
    // stop yet must not keep its overlay process alive beside a new one.
    GEN.fetch_add(1, Ordering::SeqCst);
    STARTED.store(false, Ordering::SeqCst);""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("generation wired")

# single instance guard in the child
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()
old = "pub fn main() -> i32 {"
new = """/// Only one overlay may exist at a time. Two of them draw two different frames,
/// which reads as "the HUD disagrees with the real crop" and is far harder to
/// diagnose than a second process that simply refuses to start.
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
