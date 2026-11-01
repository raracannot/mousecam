import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
drop = ("let mut win_w: i32 = 0;", "let mut win_h: i32 = 0;",
        "let mut last_move = std::time::Instant::now() - std::time::Duration::from_secs(1);",
        "let mut drag_logged = false;")
n = 0
out = []
for l in lines:
    if l.strip() in drop:
        n += 1
        continue
    out.append(l)
# drop the comment block that described the old grow-only policy if it is orphaned
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
print("removed", n, "dead declarations")
