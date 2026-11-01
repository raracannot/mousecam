import io

# register the module
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
if "pub mod single;" not in s:
    s = s.replace("pub mod hud;", "pub mod hud;\npub mod single;")
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("module registered")

# wire it into startup, and finalise a recording before the window closes
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
old = """    if std::env::args().any(|a| a == "--hud") {
        std::process::exit(mc_engine::hud_proc::main());
    }"""
new = """    if std::env::args().any(|a| a == "--hud") {
        std::process::exit(mc_engine::hud_proc::main());
    }

    // One instance only: a second copy would fight over the screen duplication.
    if !mc_engine::single::claim_single_instance() {
        mc_engine::single::focus_existing_window();
        std::process::exit(0);
    }"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("single instance wired")
