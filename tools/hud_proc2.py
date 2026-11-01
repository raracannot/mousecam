import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
i = next(i for i, l in enumerate(lines) if l.strip() == "fn main() {")
lines[i+1:i+1] = [
    "    // `--hud` runs only the overlay: no Tauri, no WebView2, no capture. It is",
    "    // spawned by the main process and exits when its stdin closes, so it can",
    "    // neither drag the UI down nor outlive the app.",
    "    if std::env::args().any(|a| a == \"--hud\") {",
    "        std::process::exit(mc_engine::hud_proc::main());",
    "    }",
    "",
]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("--hud entry point added")
