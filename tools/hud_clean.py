import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
out = []
for l in lines:
    s = l.strip()
    if s == "let mut did_move = false;":
        continue
    if s == "did_move = true;":
        continue
    out.append(l)
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
print("did_move removed")
