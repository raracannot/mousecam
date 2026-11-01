//! The overlay as its own process.
//!
//! `mousecam.exe --hud` runs this and nothing else: no Tauri, no WebView2, no
//! capture. It owns one layered window and a real message loop, which is the
//! part the in-process version could not have (pumping messages there re-entered
//! the paint path and deadlocked on the state lock).
//!
//! The parent feeds it over stdin, one line per change:
//!
//! ```text
//! cfg 2 1 1                             thickness, label, brackets
//! frame 100 200 1280 720 0 0 2560 1440   crop rect, then the monitor rect
//! show / hide
//! ```
//!
//! When the parent dies its end of the pipe closes, `read_line` returns EOF and
//! this process exits - so a crash can never leave an orphaned border on screen.

use std::io::{BufRead, Write};
use std::sync::{Mutex, OnceLock};

use windows::core::w;
use windows::Win32::Foundation::{COLORREF, HWND, LPARAM, LRESULT, RECT, WPARAM};
use windows::Win32::Graphics::Gdi::{CreateSolidBrush, DeleteObject, HBRUSH};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;
use windows::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DispatchMessageW, GetMessageW, RegisterClassW, SetTimer,
    SetWindowDisplayAffinity, ShowWindow, TranslateMessage, CS_HREDRAW, CS_VREDRAW, HTTRANSPARENT,
    LWA_COLORKEY, MA_NOACTIVATE, MSG, SW_HIDE, SW_SHOWNOACTIVATE, WM_DESTROY, WM_MOUSEACTIVATE,
    WM_NCHITTEST, WM_TIMER, WNDCLASSW, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
    WS_EX_TOPMOST, WS_EX_TRANSPARENT, WS_POPUP, WDA_EXCLUDEFROMCAPTURE,
};

use crate::hud::{paint, HudConfig, Surface};

#[derive(Clone, Copy, PartialEq)]
struct Frame {
    x: i32,
    y: i32,
    w: i32,
    h: i32,
    mon_x: i32,
    mon_y: i32,
    mon_w: i32,
    mon_h: i32,
}

#[derive(Clone, PartialEq)]
struct View {
    enabled: bool,
    frame: Option<Frame>,
    label: String,
    cfg: HudConfig,
}

impl HudConfig {
    fn eq(&self, o: &HudConfig) -> bool {
        self.thickness == o.thickness && self.show_label == o.show_label && self.brackets == o.brackets
    }
}

static VIEW: OnceLock<Mutex<View>> = OnceLock::new();

fn view() -> &'static Mutex<View> {
    VIEW.get_or_init(|| {
        Mutex::new(View {
            enabled: true,
            frame: None,
            label: String::new(),
            cfg: HudConfig::default(),
        })
    })
}

/// Parses one command line. Returns false when the parent asked us to quit.
fn apply(line: &str) -> bool {
    let mut it = line.split_whitespace();
    match it.next() {
        Some("cfg") => {
            let t: i32 = it.next().and_then(|v| v.parse().ok()).unwrap_or(2);
            let l = it.next().map(|v| v == "1").unwrap_or(true);
            let b = it.next().map(|v| v == "1").unwrap_or(true);
            let mut v = view().lock().unwrap();
            v.cfg = HudConfig { thickness: t, show_label: l, brackets: b };
        }
        Some("frame") => {
            let rest: Vec<&str> = it.collect();
            crate::mc_debug!("hud-proc", "frame {}", rest.join(" "));
            let n: Vec<i32> = rest.iter().filter_map(|v| v.parse().ok()).collect();
            if n.len() >= 8 {
                let mut v = view().lock().unwrap();
                v.frame = Some(Frame {
                    x: n[0], y: n[1], w: n[2], h: n[3],
                    mon_x: n[4], mon_y: n[5], mon_w: n[6], mon_h: n[7],
                });
            }
        }
        Some("label") => {
            let mut v = view().lock().unwrap();
            v.label = it.collect::<Vec<_>>().join(" ");
        }
        Some("show") => {
            crate::mc_info!("hud-proc", "show");
            view().lock().unwrap().enabled = true;
        }
        Some("hide") => {
            crate::mc_info!("hud-proc", "hide");
            view().lock().unwrap().enabled = false;
        }
        Some("quit") => return false,
        _ => {}
    }
    true
}

/// Only one overlay may exist at a time. Two of them draw two different frames,
/// which reads as "the HUD disagrees with the real crop" and is far harder to
/// diagnose than a second process that simply refuses to start.
fn already_running() -> bool {
    // The window itself is the marker: while another overlay lives, its window
    // exists, and it cannot outlive its process. No extra kernel object needed.
    use windows::Win32::UI::WindowsAndMessaging::FindWindowW;
    unsafe { FindWindowW(w!("MouseCamHudProc"), windows::core::PCWSTR::null()).is_ok() }
}

pub fn main() -> i32 {
    if already_running() {
        return 0;
    }

    // This process never runs Tauri, so nothing has told Windows what it is. A
    // process with no DPI awareness gets its coordinates virtualised: the window
    // lands somewhere else and is drawn at the scaled size, which looks exactly
    // like the frame being wrong. The parent works in physical pixels, so the
    // overlay must too.
    let log_path = std::env::var("MC_HUD_LOG")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::current_exe()
                .ok()
                .and_then(|p| p.parent().map(|d| d.join("mousecam.hud.log")))
                .unwrap_or_else(|| std::path::PathBuf::from("mousecam.hud.log"))
        });
    crate::log::init(log_path, true);

    unsafe {
        use windows::Win32::UI::HiDpi::{
            SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
        };
        match SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2) {
            Ok(()) => crate::mc_info!("hud-proc", "dpi awareness set to per-monitor-v2"),
            Err(e) => crate::mc_warn!("hud-proc", "could not set dpi awareness: {e}"),
        }
    }
    // Read the parent's feed on a worker thread; the main thread owns the window
    // and runs the message loop, so Win32 always sees a responsive window.
    std::thread::Builder::new()
        .name("hud-in".into())
        .spawn(|| {
            let stdin = std::io::stdin();
            let mut line = String::new();
            let mut lock = stdin.lock();
            loop {
                line.clear();
                match lock.read_line(&mut line) {
                    Ok(0) | Err(_) => {
                        // parent gone: nothing to draw any more
                        std::process::exit(0);
                    }
                    Ok(_) => {
                        if !apply(line.trim()) {
                            std::process::exit(0);
                        }
                    }
                }
            }
        })
        .ok();

    unsafe { run() }
}

unsafe fn run() -> i32 {
    let hinst = GetModuleHandleW(None).unwrap_or_default();
    let class = WNDCLASSW {
        style: CS_HREDRAW | CS_VREDRAW,
        lpfnWndProc: Some(wndproc),
        hInstance: hinst.into(),
        lpszClassName: w!("MouseCamHudProc"),
        ..Default::default()
    };
    let _ = RegisterClassW(&class);

    let hwnd = match CreateWindowExW(
        WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE,
        w!("MouseCamHudProc"),
        w!("MouseCam HUD"),
        WS_POPUP,
        0,
        0,
        100,
        100,
        None,
        None,
        Some(hinst.into()),
        None,
    ) {
        Ok(h) => h,
        Err(_) => return 1,
    };

    // 33 Hz: fast enough to track the camera, cheap enough to ignore.
    SetTimer(Some(hwnd), 1, 33, None);

    let mut msg = MSG::default();
    while GetMessageW(&mut msg, None, 0, 0).0 > 0 {
        let _ = TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    0
}

struct Painter {
    surface: Option<Surface>,
    last: Option<View>,
}

// The surface holds raw DIB pointers and is only ever touched from the window's
// own thread (WM_TIMER), so it lives in a thread-local rather than a Mutex.
thread_local! {
    static PAINTER: std::cell::RefCell<Painter> =
        std::cell::RefCell::new(Painter { surface: None, last: None });
}

unsafe fn repaint(hwnd: HWND) {
    let v = { view().lock().unwrap().clone() };
    let Some(f) = v.frame else {
        let _ = ShowWindow(hwnd, SW_HIDE);
        return;
    };
    if !v.enabled || f.w < 8 || f.h < 8 {
        let _ = ShowWindow(hwnd, SW_HIDE);
        return;
    }

    let pad = v.cfg.thickness.clamp(1, 8) + 2;
    let need_w = f.w + pad * 2;
    let need_h = f.h + pad * 2;
    let (ww, wh) = (need_w.max(16), need_h.max(16));

    PAINTER.with(|cell| {
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
    });
}

unsafe extern "system" fn wndproc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    match msg {
        WM_TIMER => {
            repaint(hwnd);
            LRESULT(0)
        }
        // The window must never take a click: a message queued here would wait
        // for a thread that is busy drawing, and the sender would stall.
        WM_NCHITTEST => LRESULT(HTTRANSPARENT as isize),
        WM_MOUSEACTIVATE => LRESULT(MA_NOACTIVATE as isize),
        WM_DESTROY => LRESULT(0),
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

/// Not used by the child (it draws with GDI into its own DIB), but keeps the
/// imports honest if a colour-key path is ever added back.
#[allow(dead_code)]
fn _unused() -> (COLORREF, HBRUSH, RECT) {
    unsafe {
        let b = CreateSolidBrush(COLORREF(0));
        let _ = DeleteObject(b.into());
        let _ = LWA_COLORKEY;
        (COLORREF(0), b, RECT::default())
    }
}
