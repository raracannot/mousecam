import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\capture.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

def idx(sub, after=0):
    for i in range(after, len(lines)):
        if sub in lines[i]:
            return i
    return -1

# 1) flag on the struct
i = idx("struct Dda {")
assert i > 0
lines[i+1:i+1] = [
    "    /// Set when the duplication died (display change, UAC, a fullscreen",
    "    /// app taking the output). The owner reopens instead of failing forever.",
    "    lost: bool,",
]

# 2) set it on a real error instead of silently returning false
i = idx("Err(_) => return false,")
assert i > 0
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines[i:i+1] = [
    ind + "// ACCESS_LOST / DEVICE_REMOVED: the duplication is dead and every later",
    ind + "// call would fail too, so tell the owner to reopen it.",
    ind + "Err(_) => {",
    ind + "    self.lost = true;",
    ind + "    return false;",
    ind + "}",
]

# 3) initialise the field where the struct is built
i = idx("have_frame: false,")
assert i > 0, "constructor not found"
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines[i+1:i+1] = [ind + "lost: false,"]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("Dda::lost wired")
