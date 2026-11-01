import io

# 1) register the module
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
if "pub mod hud_proc;" not in s:
    s = s.replace("pub mod hud;", "pub mod hud;\npub mod hud_proc;")
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("hud_proc registered")

# 2) the child entry point, before anything Tauri-ish is touched
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = "fn main() {\n    // Open the log before anything else"
new = """fn main() {
    // `--hud` runs only the overlay: no Tauri, no WebView2, no capture. It is
    // spawned by the main process and exits when its stdin closes, so it can
    // neither drag the UI down nor outlive the app.
    if std::env::args().any(|a| a == "--hud") {
        std::process::exit(mc_engine::hud_proc::main());
    }

    // Open the log before anything else"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("--hud entry point added")
