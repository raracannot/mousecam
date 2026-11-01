import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

start = next(i for i, l in enumerate(lines) if l.strip() == "match want {")
none_i = next(i for i in range(start, len(lines)) if lines[i].strip() == "None => {")

# the body I wrote sits between the match and the None arm, missing its header
# and indented one level too little
body = lines[start+1:none_i]
while body and body[-1].strip() == "":
    body.pop()
body = [("    " + l if l.strip() else l) for l in body]

ind = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
arm_ind = ind + "    "
new_block = [arm_ind + "Some(r) => {"] + body + [arm_ind + "}"]
lines[start+1:none_i] = new_block + [""]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("arm header and indentation restored")
