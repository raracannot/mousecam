import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# 1) a publish counter, so the log can prove the preview engine is still producing
i = next(i for i, l in enumerate(lines) if l.strip() == "let mut tick: u64 = 0;")
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines[i+1:i+1] = [
    ind + "// The preview path used to be completely silent, so a frozen or black",
    ind + "// preview left no trace at all. These two counters fix that.",
    ind + "let mut published: u64 = 0;",
    ind + "let mut grab_fails: u64 = 0;",
]

# 2) log grab failures
i = next(i for i, l in enumerate(lines) if "if tick % 16 == 0 && cap.grab(&mut buf) {" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
# find the closing brace of that if-block: the first line at the same indent starting with "}"
j = i + 1
while not (lines[j].startswith(ind + "}") and len(lines[j]) - len(lines[j].lstrip()) == len(ind)):
    j += 1
lines[j+1:j+1] = [
    ind + "} else if tick % 16 == 0 {",
    ind + "    grab_fails += 1;",
    ind + "    if grab_fails % 20 == 1 {",
    ind + "        mc_engine::mc_warn!(\"preview\", \"capture grab failed ({} times)\", grab_fails);",
    ind + "    }",
]

# 3) periodic proof that frames are being produced
i = next(i for i, l in enumerate(lines) if "rs.prep(lx as f32, ly as f32, rw as f32, rh as f32, pw, ph);" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines[i:i] = [
    ind + "published += 1;",
    ind + "if published % 90 == 0 {",
    ind + "    mc_engine::mc_debug!(\"preview\", \"{} frames published, crop {}x{}\", published, rw, rh);",
    ind + "}",
]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("preview path instrumented")
