import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# A hotkey-started recording used to pass hw=None and always fell back to x264.
# Resolve the preference once and remember it, so F9 and the button behave alike.
rep("""    mc_engine::mc_info!("record", "start: monitor={:?} hw={:?}", monitor, hw);""",
"""    // None means "no explicit choice" (the hotkey path): use the saved
    // preference, but only when this machine can actually encode in hardware.
    let hw = Some(hw.unwrap_or_else(|| settings().hw_encode && nvenc_available()));
    mc_engine::mc_info!("record", "start: monitor={:?} hw={:?}", monitor, hw);""")

rep("""        *last_start().lock().unwrap() = (edit.clone(), monitor, None);""",
"""        *last_start().lock().unwrap() = (edit.clone(), monitor, hw);""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("hotkey recordings now follow the hardware-encode preference")
