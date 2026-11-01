import io

# ---------------- log: tell the caller whether the file opened -------------
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\log.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("log.rs: matched %d for %s" % (c, old[:100]))
    s = s.replace(old, new)

rep("""/// Opens the log, rotating the previous one if it has grown too large.
pub fn init(path: PathBuf, verbose: bool) {""",
"""/// Opens the log, rotating the previous one if it has grown too large.
/// Returns false when the file could not be opened (a read-only install dir,
/// for example) so the caller can fall back to another location.
pub fn init(path: PathBuf, verbose: bool) -> bool {""")

rep("""    let file = OpenOptions::new().create(true).append(true).open(&path).ok();
    let mut s = cell().lock().unwrap();
    s.file = file;
    s.path = path;
    s.verbose = verbose;
}""",
"""    let file = OpenOptions::new().create(true).append(true).open(&path).ok();
    let opened = file.is_some();
    if let Ok(mut s) = cell().lock() {
        s.file = file;
        s.path = path;
        s.verbose = verbose;
    }
    opened
}""")

# stderr must never be written while the sink lock is held: a write failure would
# panic inside log(), and the panic hook would then try to take the same lock.
rep("""    // stderr as well, so a terminal run shows it live
    eprint!("{line}");
    if let Some(f) = s.file.as_mut() {
        let _ = f.write_all(line.as_bytes());
        let _ = f.flush();
    }""",
"""    if let Some(f) = s.file.as_mut() {
        let _ = f.write_all(line.as_bytes());
        let _ = f.flush();
    }
    drop(s);
    // stderr as well, so a terminal run shows it live
    eprint!("{line}");""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("log.rs updated")
