import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\recorder.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:90]))
    s = s.replace(old, new)

# a failed write means the file is already damaged; carrying on produces a
# "successful" recording that will not open
rep("""        if let Some(m) = master.as_mut() {
            let _ = m.write_frame(&frame_buf);
        }""",
"""        if let Some(m) = master.as_mut() {
            if let Err(e) = m.write_frame(&frame_buf) {
                write_err = Some(format!("写入原片失败: {e}"));
                break;
            }
        }""")

rep("""            let _ = camera.write_frame(&crop_buf);""",
"""            if let Err(e) = camera.write_frame(&crop_buf) {
                write_err = Some(format!("写入跟拍成片失败: {e}"));
                break;
            }""")

# declare the error slot next to the other loop state
i = s.index("    let mut dropped = 0;")
s = s[:i] + "    let mut write_err: Option<String> = None;\n" + s[i:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("write errors captured")
