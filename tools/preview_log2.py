import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# remove the misplaced block (the else-if that attached itself to the while loop)
i = next(i for i, l in enumerate(lines) if "} else if tick % 16 == 0 {" in l)
del lines[i:i+6]                       # else-if line .. closing brace
while lines[i].strip() == "":
    del lines[i]

# attach it to the grab-if instead: that block ends on the line above
j = i - 1
assert lines[j].strip() == "}", (j, lines[j])
ind = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
lines[j] = ind + "} else if tick % 16 == 0 {"
lines[j+1:j+1] = [
    ind + "    grab_fails += 1;",
    ind + "    if grab_fails % 20 == 1 {",
    ind + "        mc_engine::mc_warn!(\"preview\", \"capture grab failed ({} times)\", grab_fails);",
    ind + "    }",
    ind + "}",
]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("else-if reattached to the grab branch")
