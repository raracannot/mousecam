import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()
old = """        WM_APP + 1 => {
            // the reader thread poked us: apply show/hide immediately
            repaint(hwnd);
            LRESULT(0)
        }"""
new = """        m if m == WM_APP + 1 => {
            // the reader thread poked us: apply show/hide immediately
            repaint(hwnd);
            LRESULT(0)
        }"""
assert s.count(old) == 1
s = s.replace(old, new)
s = s.replace("WM_MOUSEACTIVATE, WM_NCHITTEST, WM_PAINT,",
              "WM_APP, WM_MOUSEACTIVATE, WM_NCHITTEST, WM_PAINT,")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("fixed")
