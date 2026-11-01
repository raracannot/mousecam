import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")
# drop the duplicate ".ok();" that the failed insertion left behind
dup = None
for i, l in enumerate(lines):
    if l.strip() == ".ok();" and lines[i-1].strip() == ".ok();":
        dup = i
        break
assert dup is not None
del lines[dup]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("removed the duplicated terminator")
