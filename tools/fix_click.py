import io

# --- 1. log path override so test runs never touch the user's log ---
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = """    let log_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join("mousecam.log")))
        .unwrap_or_else(|| PathBuf::from("mousecam.log"));"""
new = """    // MC_LOG lets a test run write its own file instead of overwriting the one a
    // user will want to send in after reproducing a bug.
    let log_path = match std::env::var("MC_LOG") {
        Ok(p) if !p.trim().is_empty() => PathBuf::from(p),
        _ => std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.join("mousecam.log")))
            .unwrap_or_else(|| PathBuf::from("mousecam.log")),
    };"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("MC_LOG added")

# --- 2. make the overlay unclickable even if the ex-style were ignored ---
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
s = s.replace("IsWindowVisible, WM_DESTROY, WM_ERASEBKGND, WM_PAINT,",
              "IsWindowVisible, MA_NOACTIVATE, HTTRANSPARENT, WM_DESTROY, WM_ERASEBKGND,\n        WM_MOUSEACTIVATE, WM_NCHITTEST, WM_PAINT,")
old = """            WM_ERASEBKGND => LRESULT(1),"""
new = """            // Belt and braces: WS_EX_TRANSPARENT should already make the window
            // click-through, but a click landing here would be queued for a
            // thread that never pumps messages - the system would then wait for
            // a response that never comes, which reads as the whole app freezing.
            WM_NCHITTEST => LRESULT(HTTRANSPARENT as isize),
            WM_MOUSEACTIVATE => LRESULT(MA_NOACTIVATE as isize),
            WM_ERASEBKGND => LRESULT(1),"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("hit-test pass-through added")
