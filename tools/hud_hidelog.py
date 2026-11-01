import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()
old = """        Some("show") => view().lock().unwrap().enabled = true,
        Some("hide") => view().lock().unwrap().enabled = false,"""
new = """        Some("show") => {
            crate::mc_info!("hud-proc", "show");
            view().lock().unwrap().enabled = true;
        }
        Some("hide") => {
            crate::mc_info!("hud-proc", "hide");
            view().lock().unwrap().enabled = false;
        }"""
assert s.count(old) == 1
s = s.replace(old, new)

# make the hide path impossible to skip: the window is hidden as soon as the
# state says so, not only on the next timer tick
old2 = """        WM_TIMER => {
            repaint(hwnd);
            LRESULT(0)
        }"""
new2 = """        WM_TIMER => {
            repaint(hwnd);
            LRESULT(0)
        }
        WM_APP + 1 => {
            // the reader thread poked us: apply show/hide immediately
            repaint(hwnd);
            LRESULT(0)
        }"""
assert s.count(old2) == 1
s = s.replace(old2, new2)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("hide/show logging added")
