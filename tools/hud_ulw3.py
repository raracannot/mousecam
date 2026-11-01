import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:100]))
    s = s.replace(old, new)

# qualify the GDI handle types on the surface struct
rep("""struct Surface {
    dc: HDC,
    bmp: HBITMAP,
    old: HGDIOBJ,""",
"""struct Surface {
    dc: windows::Win32::Graphics::Gdi::HDC,
    bmp: windows::Win32::Graphics::Gdi::HBITMAP,
    old: windows::Win32::Graphics::Gdi::HGDIOBJ,""")

rep("        let old = SelectObject(dc, bmp);",
    "        let old = SelectObject(dc, windows::Win32::Graphics::Gdi::HGDIOBJ(bmp.0));")
rep("            let _ = windows::Win32::Graphics::Gdi::DeleteObject(bmp);",
    "            let _ = windows::Win32::Graphics::Gdi::DeleteObject(windows::Win32::Graphics::Gdi::HGDIOBJ(bmp.0));")
rep("            let _ = DeleteObject(self.bmp);",
    "            let _ = DeleteObject(windows::Win32::Graphics::Gdi::HGDIOBJ(self.bmp.0));")

# WM_PAINT no longer paints: the surface is pushed with UpdateLayeredWindow
rep("""                // No rect: paint the frame against the whole client, which is
                // exactly the right thing after a resize.
                paint(hwnd, &label, cfg, None);""",
"""                // Nothing to do: the compositor is fed with UpdateLayeredWindow
                // from the main loop, so WM_PAINT has no work here.
                let _ = (&label, cfg);""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("types and WM_PAINT fixed")
