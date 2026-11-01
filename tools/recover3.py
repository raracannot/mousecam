import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# add the recovery function next to log_context
i = next(k for k, l in enumerate(lines) if l.strip() == "fn log_context() {")
doc = i - 1
lines[doc:doc] = [
    "/// Adopts recordings that a crash or a forced close left without a meta.json.",
    "/// Runs off the main thread because it may call ffmpeg to learn a duration.",
    "fn recover_orphans() {",
    "    let n = mc_api::recover_orphan_clips();",
    "    if n > 0 {",
    "        mc_engine::mc_warn!(\"app\", \"recovered {n} interrupted recording(s)\");",
    "    }",
    "}",
    "",
]

# start it next to the other startup thread
j = next(k for k, l in enumerate(lines) if l.strip() == ".spawn(log_context)")
ind = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
lines[j+1:j+1] = [
    ind + "std::thread::Builder::new()",
    ind + "    .name(\"recover\".into())",
    ind + "    .spawn(recover_orphans)",
    ind + "    .ok();",
]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("recovery threaded at startup")
