import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

rep("const QUIET_CALLS = new Set(['preview_frame', 'record_status', 'hud_get', 'hud_get_config', 'media_path', 'still']);",
    "const QUIET_CALLS = new Set(['preview_frame', 'record_status', 'hud_get', 'hud_get_config', 'media_path', 'still', 'heartbeat']);")

rep("""/* ---- boot: load the saved settings before the first paint ---- */""",
"""/* ---- boot: tell the watchdog the UI thread is alive ---- */
// Webview timers only run while the UI thread is pumping; a gap in these beats
// is what the Rust watchdog reports as a stall.
if (IS_TAURI) {
  setInterval(() => {
    invoke('heartbeat').catch(() => {});
  }, 2000);
}

/* ---- boot: load the saved settings before the first paint ---- */""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("heartbeat sender installed")
