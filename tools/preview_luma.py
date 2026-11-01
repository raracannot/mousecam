import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

i = next(i for i, l in enumerate(lines) if "published += 1;" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
# after the resample + sink publish, sample the OUTPUT buffer: a black image here
# means the preview pipeline produced nothing, regardless of the frame counter.
j = next(j for j in range(i, len(lines)) if "px: out.clone()," in lines[j])
k = next(k for k in range(j, len(lines)) if lines[k].strip() == "});")
ind2 = lines[k][:len(lines[k]) - len(lines[k].lstrip())]
lines[k+1:k+1] = [
    ind2 + "// A frame counter alone cannot tell \"producing\" from \"producing black\".",
    ind2 + "// Sample the output so a black preview says so in the log.",
    ind2 + "if published % 45 == 0 {",
    ind2 + "    let step = (out.len() / 512).max(4);",
    ind2 + "    let sum: u64 = out.iter().step_by(step).map(|&v| (v >> 16 & 0xFF) as u64",
    ind2 + "        + (v >> 8 & 0xFF) as u64 + (v & 0xFF) as u64).sum();",
    ind2 + "    let n = (out.len() / step).max(1) as u64;",
    ind2 + "    let luma = sum / (n * 3);",
    ind2 + "    if luma < 6 {",
    ind2 + "        mc_engine::mc_warn!(\"preview\", \"published frame {} is BLACK (luma {})\", published, luma);",
    ind2 + "    } else {",
    ind2 + "        mc_engine::mc_debug!(\"preview\", \"frame {} luma {} crop {}x{}\", published, luma, rw, rh);",
    ind2 + "    }",
    ind2 + "}",
]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("preview luminance logging added")
