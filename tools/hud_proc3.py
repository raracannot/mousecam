import io

# Surface dimensions must be readable by the child
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
s = s.replace("""    bits: *mut u32,
    w: i32,
    h: i32,
}""", """    bits: *mut u32,
    pub(crate) w: i32,
    pub(crate) h: i32,
}""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("Surface fields exposed")

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()

# frame parsing: collect once
old = """        Some("frame") => {
            let n: Vec<i32> = it.filter_map(|v| v.parse().ok()).collect();
            if n.len() >= 8 {
                let mut v = view().lock().unwrap();
                v.frame = Some(Frame {
                    x: n[0], y: n[1], w: n[2], h: n[3],
                    mon_x: n[4], mon_y: n[5], mon_w: n[6], mon_h: n[7],
                });
                v.label = it.next().unwrap_or("").to_string(); // never present; see below
            }
        }"""
new = """        Some("frame") => {
            let rest: Vec<&str> = it.collect();
            let n: Vec<i32> = rest.iter().filter_map(|v| v.parse().ok()).collect();
            if n.len() >= 8 {
                let mut v = view().lock().unwrap();
                v.frame = Some(Frame {
                    x: n[0], y: n[1], w: n[2], h: n[3],
                    mon_x: n[4], mon_y: n[5], mon_w: n[6], mon_h: n[7],
                });
            }
        }"""
assert s.count(old) == 1
s = s.replace(old, new)

# the surface owns raw pointers and must stay on the window thread
old2 = """static PAINTER: OnceLock<Mutex<Painter>> = OnceLock::new();

fn painter() -> &'static Mutex<Painter> {
    PAINTER.get_or_init(|| Mutex::new(Painter { surface: None, last: None }))
}"""
new2 = """// The surface holds raw DIB pointers and is only ever touched from the window's
// own thread (WM_TIMER), so it lives in a thread-local rather than a Mutex.
thread_local! {
    static PAINTER: std::cell::RefCell<Painter> =
        std::cell::RefCell::new(Painter { surface: None, last: None });
}"""
assert s.count(old2) == 1
s = s.replace(old2, new2)

old3 = """    let mut p = painter().lock().unwrap();
    let stale = p.surface.as_ref().map(|s| (s.w, s.h) != (ww, wh)).unwrap_or(true);
    if stale {
        p.surface = Surface::new(ww, wh);
    }
    let Some(s) = p.surface.as_mut() else {
        return;
    };
    if paint(hwnd, s, f.x - pad, f.y - pad, &v.label, v.cfg, Some((pad, pad, f.w, f.h))) {
        p.last = Some(v);
        let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);
        let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);
    }"""
new3 = """    PAINTER.with(|cell| {
        let mut p = cell.borrow_mut();
        let stale = p.surface.as_ref().map(|s| (s.w, s.h) != (ww, wh)).unwrap_or(true);
        if stale {
            p.surface = Surface::new(ww, wh);
        }
        let Some(s) = p.surface.as_mut() else {
            return;
        };
        if paint(hwnd, s, f.x - pad, f.y - pad, &v.label, v.cfg, Some((pad, pad, f.w, f.h))) {
            p.last = Some(v);
            let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);
            let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);
        }
    });"""
assert s.count(old3) == 1
s = s.replace(old3, new3)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("thread-local painter")
