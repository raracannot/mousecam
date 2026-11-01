import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\capture.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# 1) mark the duplication as lost instead of just returning false
rep("""                    Err(e) if e.code() == DXGI_ERROR_WAIT_TIMEOUT => return self.have_frame,
                    Err(_) => return false,""",
"""                    Err(e) if e.code() == DXGI_ERROR_WAIT_TIMEOUT => return self.have_frame,
                    // ACCESS_LOST (display mode change, UAC, a fullscreen app taking the
                    // output) or DEVICE_REMOVED: the duplication is dead and every later
                    // call would keep failing. Flag it so the owner reopens immediately.
                    Err(_) => {
                        self.lost = true;
                        return false;
                    }""")

# 2) the flag lives on the Dda
i = s.index("pub struct Dda")
j = s.index("{", i)
k = s.index("}", j)
body = s[j:k]
if "lost" not in body:
    s = s[:k] + "    /// Set when the duplication died; the owner reopens it.\n    lost: bool,\n" + s[k:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("Dda::lost flag added")
