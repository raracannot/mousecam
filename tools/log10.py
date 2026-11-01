import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\log.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for: %s" % (c, old[:120]))
    s = s.replace(old, new)

rep("""struct Sink {
    file: Option<File>,
    path: PathBuf,
    verbose: bool,
}""",
"""struct Sink {
    file: Option<File>,
    path: PathBuf,
    verbose: bool,
    /// Key of the last message written, and how many identical ones followed.
    /// A poller that fails at 8 Hz would otherwise bury everything else.
    last: String,
    repeats: u32,
}""")

rep("""            file: None,
            path: PathBuf::from("mousecam.log"),
            verbose: false,
        })""",
"""            file: None,
            path: PathBuf::from("mousecam.log"),
            verbose: false,
            last: String::new(),
            repeats: 0,
        })""")

rep("""    let line = format!(
        "{}  {}  [{:<10}] {}\\n",
        stamp(),
        level.tag(),
        truncate(target, 10),
        msg
    );
    // stderr as well, so a terminal run shows it live
    eprint!("{line}");
    if let Ok(mut s) = cell().lock() {
        if let Some(f) = s.file.as_mut() {
            let _ = f.write_all(line.as_bytes());
            let _ = f.flush();
        }
    }""",
"""    let key = format!("{}{}{}", level.tag(), target, msg);
    let mut s = match cell().lock() {
        Ok(s) => s,
        Err(_) => return,
    };

    if s.last == key {
        s.repeats = s.repeats.saturating_add(1);
        return;
    }

    let mut line = String::new();
    if s.repeats > 0 {
        line.push_str(&format!(
            "{}  {}  [{:<10}] ... 上一行又重复了 {} 次\\n",
            stamp(),
            "WARN ",
            "repeat",
            s.repeats
        ));
        s.repeats = 0;
    }
    line.push_str(&format!(
        "{}  {}  [{:<10}] {}\\n",
        stamp(),
        level.tag(),
        truncate(target, 10),
        msg
    ));
    s.last = key;

    // stderr as well, so a terminal run shows it live
    eprint!("{line}");
    if let Some(f) = s.file.as_mut() {
        let _ = f.write_all(line.as_bytes());
        let _ = f.flush();
    }""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("log dedupe added")

# the UI poller is expected to fail while the preview warms up
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = """function traced(fn) {
  return async (cmd, args) => {
    try {
      return await fn(cmd, args);
    } catch (e) {
      logUi('error', `调用 ${cmd} 失败: ${e}`);
      throw e;
    }
  };
}"""
new = """// Commands that are expected to fail now and then (the preview poller runs
// before the engine is ready) would otherwise flood the log at 8 lines/second.
const QUIET_CALLS = new Set(['preview_frame', 'record_status', 'hud_get', 'hud_get_config']);

function traced(fn) {
  return async (cmd, args) => {
    try {
      return await fn(cmd, args);
    } catch (e) {
      if (!QUIET_CALLS.has(cmd)) logUi('error', `调用 ${cmd} 失败: ${e}`);
      throw e;
    }
  };
}"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("quiet calls added")
