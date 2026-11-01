import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\capture.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
i = next(i for i, l in enumerate(lines) if "let ok = if let Some(dda) = self.dda.as_mut() {" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
b = ind + "    "
new = [
    ind + "let mon = self.mon;",
    ind + "let ok = if let Some(dda) = self.dda.as_mut() {",
    b + "// Reopen the moment the duplication dies instead of waiting for 20",
    b + "// failed frames: until it is reopened the preview and the recording",
    b + "// both show a frozen picture and nobody can tell why.",
    b + "if dda.lost {",
    b + "    crate::mc_warn!(\"capture\", \"duplication lost - reopening\");",
    b + "    match Dda::open(mon) {",
    b + "        Some(fresh) => {",
    b + "            *dda = fresh;",
    b + "            self.fails = 0;",
    b + "            crate::mc_info!(\"capture\", \"duplication reopened\");",
    b + "        }",
    b + "        None => {",
    b + "            crate::mc_warn!(\"capture\", \"reopen failed, will retry next frame\");",
    b + "        }",
    b + "    }",
    b + "    false",
    b + "} else {",
    b + "    let r = dda.grab(dst, w, h);",
    b + "    if !r {",
    b + "        self.fails += 1;",
    b + "        if self.fails > 20 {",
    b + "            self.fails = 0;",
    b + "            match Dda::open(mon) {",
    b + "                Some(fresh) => {",
    b + "                    *dda = fresh;",
    b + "                    crate::mc_warn!(\"capture\", \"duplication reopened after 20 failed frames\");",
    b + "                }",
    b + "                None => {}",
    b + "            }",
    b + "        }",
    b + "    } else {",
    b + "        self.fails = 0;",
    b + "    }",
    b + "    r",
    b + "}",
    ind + "} else if let Some(blt) = self.blt.as_mut() {",
]
# replace lines i .. i+14 (the old block up to and including `r` and the closing brace)
end = i
for j in range(i, i + 30):
    if lines[j].strip() == "} else if let Some(blt) = self.blt.as_mut() {":
        end = j
        break
lines[i:end+1] = new
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("immediate reopen installed")
