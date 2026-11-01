//! On-screen viewfinder HUD: a click-through, always-on-top frame that shows
//! exactly what the follow-cam is capturing.
//!
//! Properties that matter:
//!  * `WDA_EXCLUDEFROMCAPTURE` keeps it out of the recording (it is drawn on the
//!    desktop, which is precisely what we capture);
//!  * the window is click-through, so it never blocks input;
//!  * it repaints only when the pixels would actually differ - moving it is a
//!    `SetWindowPos` and needs no repaint at all.
//!
//! There is deliberately no dim / spotlight mode: it needed a second full-screen
//! layered window whose region is cut every time the camera moves, and getting
//! the DPI mapping, the colour key and the alpha right on top of an already
//! fragile layered window was not worth the risk. The frame alone is enough to
//! show what is being captured.

use crate::camera::IRect;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};

/// Appearance knobs exposed in the recorder UI.
#[derive(Clone, Copy, PartialEq)]
pub struct HudConfig {
    /// Frame stroke width in pixels.
    pub thickness: i32,
    pub show_label: bool,
    pub brackets: bool,
}

impl Default for HudConfig {
    fn default() -> Self {
        Self {
            thickness: 2,
            show_label: true,
            brackets: true,
        }
    }
}

struct HudState {
    rect: Option<IRect>,
    /// Display being recorded. The overlay is a fixed slab covering it, so the
    /// frame can follow the camera by repainting instead of by moving a window.
    monitor: Option<IRect>,
    label: String,
    enabled: bool,
    cfg: HudConfig,
}

static STATE: OnceLock<Mutex<HudState>> = OnceLock::new();
/// Bumped by every start()/stop(): a supervisor only owns the overlay while the
/// generation it was created in is still current.
static GEN: AtomicU64 = AtomicU64::new(0);

static STARTED: AtomicBool = AtomicBool::new(false);

fn state() -> &'static Mutex<HudState> {
    STATE.get_or_init(|| {
        Mutex::new(HudState {
            rect: None,
            monitor: None,
            label: String::new(),
            enabled: true,
            cfg: HudConfig::default(),
        })
    })
}

/// Ask the HUD to frame `rect` (screen coordinates). `None` hides it.
pub fn set_rect(rect: Option<IRect>, label: &str) {
    let mut g = state().lock().unwrap();
    g.rect = rect;
    g.label.clear();
    g.label.push_str(label);
}

/// Same, plus the monitor. The monitor is only used to derive the DPI mapping,
/// which is why it is still accepted after the dim layer went away.
pub fn set_frame(rect: Option<IRect>, monitor: Option<IRect>, label: &str) {
    set_rect(rect, label);
    if let Ok(mut g) = state().lock() {
        g.monitor = monitor;
    }
}

pub fn set_config(cfg: HudConfig) {
    state().lock().unwrap().cfg = cfg;
}

pub fn config() -> HudConfig {
    state().lock().unwrap().cfg
}

pub fn set_enabled(on: bool) {
    state().lock().unwrap().enabled = on;
}

pub fn enabled() -> bool {
    state().lock().unwrap().enabled
}

/// Starts the HUD thread. Safe to call more than once.
/// True when the foreground window belongs to this process (and is not the
/// overlay itself). The overlay is hidden then: it is only useful while another
/// application is being recorded, and keeping a topmost layered window parked
/// over our own WebView2 window is exactly the interaction that made the UI
/// stop composing.
unsafe fn app_in_foreground(hud: windows::Win32::Foundation::HWND) -> bool {
    use windows::Win32::UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowThreadProcessId};
    let fg = GetForegroundWindow();
    if fg.is_invalid() || fg == hud {
        return false;
    }
    let mut pid = 0u32;
    GetWindowThreadProcessId(fg, Some(&mut pid));
    pid == std::process::id()
}

static HUD_AWARE: AtomicBool = AtomicBool::new(false);

pub fn start() {
    if STARTED.swap(true, Ordering::SeqCst) {
        return;
    }
    std::thread::Builder::new()
        .name("mc-hud".into())
        .spawn(|| {
            if std::env::var_os("MC_HUD_INPROC").is_some() {
                unsafe { run() }
            } else {
                let me = GEN.fetch_add(1, Ordering::SeqCst) + 1;
                run_remote(me);
                if GEN.load(Ordering::SeqCst) == me {
                    STARTED.store(false, Ordering::SeqCst);
                }
            }
        })
        .ok();
}

/// Feeds the overlay process. The child owns the window and a real message loop;
/// this side only writes a line when the state actually changes.
///
/// Isolation is the point: if the overlay dies the recording does not, and if the
/// parent dies the pipe closes so the child exits on EOF - no orphan can be left
/// drawing a stale border over the desktop.
fn run_remote(me: u64) {
    use std::io::Write;
    use std::os::windows::process::CommandExt;
    use std::process::{Child, ChildStdin, Command, Stdio};

    let exe = match std::env::current_exe() {
        Ok(p) => p,
        Err(_) => return,
    };
    let mut child: Option<Child> = None;
    let mut stdin: Option<ChildStdin> = None;
    let mut last = String::new();
    // A child that dies immediately would otherwise be respawned every 33 ms,
    // which turns one configuration problem into a process storm.
    let mut backoff_ms: u64 = 0;
    let mut spawned_at = std::time::Instant::now();

    while STARTED.load(Ordering::SeqCst) && GEN.load(Ordering::SeqCst) == me {
        if stdin.is_none() {
            if backoff_ms > 0 {
                let deadline = std::time::Instant::now() + std::time::Duration::from_millis(backoff_ms);
                while std::time::Instant::now() < deadline {
                    if !STARTED.load(Ordering::SeqCst) || GEN.load(Ordering::SeqCst) != me {
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(50));
                }
            }
            let spawned = Command::new(&exe)
                .arg("--hud")
                .stdin(Stdio::piped())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .creation_flags(0x0800_0000) // CREATE_NO_WINDOW
                .spawn();
            match spawned {
                Ok(mut c) => {
                    stdin = c.stdin.take();
                    child = Some(c);
                    last.clear();
                    spawned_at = std::time::Instant::now();
                    crate::mc_info!("hud", "overlay process started");
                }
                Err(e) => crate::mc_warn!("hud", "cannot start the overlay process: {e}"),
            }
        }

        let (rect, enabled, label, cfg, mon) = {
            let g = state().lock().unwrap();
            (g.rect, g.enabled, g.label.clone(), g.cfg, g.monitor)
        };

        let mut buf = String::new();
        buf.push_str(&format!(
            "cfg {} {} {}\n",
            cfg.thickness,
            cfg.show_label as i32,
            cfg.brackets as i32
        ));
        buf.push_str(&format!("label {}\n", label));
        buf.push_str(if enabled { "show\n" } else { "hide\n" });
        if let (Some(r), Some(m)) = (rect, mon) {
            if r.w > 8 && r.h > 8 {
                buf.push_str(&format!(
                    "frame {} {} {} {} {} {} {} {}\n",
                    r.x, r.y, r.w, r.h, m.x, m.y, m.w, m.h
                ));
            }
        }

        if buf != last {
            if let Some(si) = stdin.as_mut() {
                if si.write_all(buf.as_bytes()).is_err() || si.flush().is_err() {
                    crate::mc_warn!("hud", "overlay pipe closed - restarting it");
                    stdin = None;
                    child = None;
                    continue;
                }
            }
            if std::env::var_os("MC_HUD_TRACE").is_some() {
                crate::mc_debug!("hud", "send {}", buf.trim().replace('\n', " | "));
            }
            last = buf;
        }

        if let Some(c) = child.as_mut() {
            if let Ok(Some(_)) = c.try_wait() {
                let lived = spawned_at.elapsed();
                backoff_ms = if lived < std::time::Duration::from_secs(2) {
                    (backoff_ms.max(100) * 2).min(5000)
                } else {
                    0
                };
                crate::mc_warn!(
                    "hud",
                    "overlay process exited after {} ms - restarting in {} ms",
                    lived.as_millis(),
                    backoff_ms
                );
                stdin = None;
                child = None;
            }
        }

        std::thread::sleep(std::time::Duration::from_millis(33));
    }

    drop(stdin);
    if let Some(mut c) = child {
        let _ = c.kill();
        let _ = c.wait();
    }
    crate::mc_info!("hud", "overlay process stopped");
}


pub fn stop() {
    // End the current generation first: a supervisor that has not noticed the
    // stop yet must not keep its overlay process alive beside a new one.
    GEN.fetch_add(1, Ordering::SeqCst);
    STARTED.store(false, Ordering::SeqCst);
    set_rect(None, "");
}

/// Mapping between the physical desktop (what DXGI reports) and the coordinate
/// space this process sees. They differ whenever the process is not per-monitor
/// DPI aware: at 125% a 2560x1440 desktop is presented as 2048x1152.
///
/// The ratio is taken from the UNION of all monitors, not from a single one -
/// using one monitor's width gave 0.53 on a 1080-wide second screen and put the
/// overlay in the wrong place.
struct DeskMap {
    sx: f32,
    sy: f32,
    left: i32,
    top: i32,
    vx: i32,
    vy: i32,
}

impl DeskMap {
    /// No conversion at all: valid when this thread is per-monitor aware, in
    /// which case window coordinates are physical pixels and already line up
    /// with the monitor rectangles from DXGI.
    const fn identity() -> Self {
        Self { sx: 1.0, sy: 1.0, left: 0, top: 0, vx: 0, vy: 0 }
    }

    unsafe fn new() -> Self {
        use windows::Win32::Foundation::{LPARAM, RECT, TRUE};
        use windows::Win32::Graphics::Gdi::{
            EnumDisplayMonitors, GetMonitorInfoW, HDC, HMONITOR, MONITORINFO,
        };
        use windows::Win32::UI::WindowsAndMessaging::{
            GetSystemMetrics, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN, SM_XVIRTUALSCREEN,
            SM_YVIRTUALSCREEN,
        };

        unsafe extern "system" fn cb(
            hmon: HMONITOR,
            _hdc: HDC,
            _rc: *mut RECT,
            data: LPARAM,
        ) -> windows::core::BOOL {
            // [left, top, right, bottom]
            let b = &mut *(data.0 as *mut [i32; 4]);
            let mut mi = MONITORINFO {
                cbSize: std::mem::size_of::<MONITORINFO>() as u32,
                ..Default::default()
            };
            if GetMonitorInfoW(hmon, &mut mi).as_bool() {
                let r = mi.rcMonitor;
                b[0] = b[0].min(r.left);
                b[1] = b[1].min(r.top);
                b[2] = b[2].max(r.right);
                b[3] = b[3].max(r.bottom);
            }
            TRUE
        }

        let mut b = [i32::MAX, i32::MAX, i32::MIN, i32::MIN];
        let _ = EnumDisplayMonitors(None, None, Some(cb), LPARAM(&mut b as *mut _ as isize));

        let vx = GetSystemMetrics(SM_XVIRTUALSCREEN);
        let vy = GetSystemMetrics(SM_YVIRTUALSCREEN);
        let vw = GetSystemMetrics(SM_CXVIRTUALSCREEN).max(1);
        let vh = GetSystemMetrics(SM_CYVIRTUALSCREEN).max(1);

        let (left, top) = if b[0] == i32::MAX { (0, 0) } else { (b[0], b[1]) };
        let (right, bottom) = if b[2] == i32::MIN { (vw, vh) } else { (b[2], b[3]) };

        let sx = ((right - left) as f32 / vw as f32).max(0.1);
        let sy = ((bottom - top) as f32 / vh as f32).max(0.1);
        Self { sx, sy, left, top, vx, vy }
    }

    /// physical screen point -> window-manager coordinate
    fn pt(&self, x: i32, y: i32) -> (i32, i32) {
        (
            self.vx + ((x - self.left) as f32 / self.sx).round() as i32,
            self.vy + ((y - self.top) as f32 / self.sy).round() as i32,
        )
    }

    fn len(&self, w: i32, h: i32) -> (i32, i32) {
        (
            (w as f32 / self.sx).round() as i32,
            (h as f32 / self.sy).round() as i32,
        )
    }
}

unsafe fn run() {
    use windows::core::w;
    use windows::Win32::Foundation::{COLORREF, HWND, LPARAM, LRESULT, WPARAM};
    use windows::Win32::System::LibraryLoader::GetModuleHandleW;
    use windows::Win32::UI::WindowsAndMessaging::{
        CreateWindowExW, DefWindowProcW, RegisterClassW, SetLayeredWindowAttributes,
        SetWindowDisplayAffinity, SetWindowPos, ShowWindow, CS_HREDRAW, CS_VREDRAW, HWND_TOPMOST,
        LWA_COLORKEY, SWP_NOACTIVATE, SWP_NOSIZE, SW_HIDE, SW_SHOWNOACTIVATE, WNDCLASSW,
        IsWindowVisible, MA_NOACTIVATE, HTTRANSPARENT, WM_DESTROY, WM_ERASEBKGND,
        WM_MOUSEACTIVATE, WM_NCHITTEST, WM_PAINT, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST,
        WS_EX_TRANSPARENT, WS_POPUP, WDA_EXCLUDEFROMCAPTURE,
    };

    const KEY: COLORREF = COLORREF(0x00FF00FF);

    unsafe extern "system" fn wndproc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
        match msg {
            WM_PAINT => {
                let (label, cfg) = match state().lock() {
                    Ok(g) => (g.label.clone(), g.cfg),
                    Err(_) => (String::new(), HudConfig::default()),
                };
                // Nothing to do: the compositor is fed with UpdateLayeredWindow
                // from the main loop, so WM_PAINT has no work here.
                let _ = (&label, cfg);
                LRESULT(0)
            }
            // Belt and braces: WS_EX_TRANSPARENT should already make the window
            // click-through, but a click landing here would be queued for a
            // thread that never pumps messages - the system would then wait for
            // a response that never comes, which reads as the whole app freezing.
            WM_NCHITTEST => LRESULT(HTTRANSPARENT as isize),
            WM_MOUSEACTIVATE => LRESULT(MA_NOACTIVATE as isize),
            WM_ERASEBKGND => LRESULT(1),
            WM_DESTROY => LRESULT(0),
            _ => DefWindowProcW(hwnd, msg, wp, lp),
        }
    }

    let hinst = GetModuleHandleW(None).unwrap_or_default();
    let class = WNDCLASSW {
        style: CS_HREDRAW | CS_VREDRAW,
        lpfnWndProc: Some(wndproc),
        hInstance: hinst.into(),
        // erase to the colour key so an exposed strip is transparent, never a
        // black bar (this window has no message pump, so WM_PAINT only runs
        // when we call paint ourselves)
        lpszClassName: w!("MouseCamHud"),
        ..Default::default()
    };
    // RegisterClassW fails if the class already exists, which is harmless on a
    // restart but must not be treated as an error.
    let _ = RegisterClassW(&class);

    // DPI awareness is fixed for a window once it exists, so declare it here
    // and not after the HWND is created.
    unsafe {
        use windows::Win32::UI::HiDpi::{SetThreadDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2};
        let _ = SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    }
    let hwnd = match CreateWindowExW(
        WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOOLWINDOW
            | WS_EX_TOPMOST
            | WS_EX_NOACTIVATE,
        w!("MouseCamHud"),
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
        Err(_) => return,
    };

    // No SetLayeredWindowAttributes: the surface comes from UpdateLayeredWindow.

    // MC_HUD_CAPTURABLE=1 skips the capture exclusion so the HUD can be
    // screenshotted during development.
    let capturable = std::env::var_os("MC_HUD_CAPTURABLE").is_some();
    // MC_HUD_CAPTURABLE=1 keeps the frame capturable for screenshots.

    let mut shown = false;
    // The surface is reused across frames: allocating a 7 MB DIB whenever
    // the crop changes size (ten times a second while the camera moves) both
    // wastes memory and can fail, which froze the overlay for good.
    let mut win_w: i32 = 0;
    let mut win_h: i32 = 0;
    let mut surf: Option<Surface> = None;
    let mut last_geom: Option<(i32, i32, i32, i32)> = None;
    let mut last_move = std::time::Instant::now() - std::time::Duration::from_secs(1);
    // The window is allowed to be larger than the frame: the colour key makes
    // the excess invisible. Resizing a layered window recreates and repaints its
    // whole surface, so it must happen rarely - moving is the cheap operation.
    // A single scale factor cannot describe two monitors with different scaling, so
    // prefer a per-monitor-aware thread, where the mapping is the identity. Set
    // before the window exists - awareness is fixed per window once created.
    let aware = unsafe {
        use windows::Win32::UI::HiDpi::{
            SetThreadDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
        };
        !SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2).0.is_null()
    };
    HUD_AWARE.store(aware, Ordering::Relaxed);
    let mut m = if aware { DeskMap::identity() } else { DeskMap::new() };
    // Only the fallback needs a refresh; the identity mapping is constant and
    // enumerating the displays 30 times a second just costs syscalls.
    let mut map_tick: u32 = 0;
    // trigger a repaint - the crop grows and shrinks with the camera speed.
    let mut last_paint_key: Option<(i32, i32, i32, i32, i32, bool, bool, String)> = None;

    while STARTED.load(Ordering::SeqCst) {
        let (rect, enabled, label, cfg, mon) = {
            let g = state().lock().unwrap();
            (g.rect, g.enabled, g.label.clone(), g.cfg, g.monitor)
        };

        map_tick = map_tick.wrapping_add(1);
        if !aware && map_tick % 150 == 0 {
            m = DeskMap::new();
        }

        let want = match rect {
            Some(r) if enabled && r.w > 8 && r.h > 8 => Some(r),
            _ => None,
        };

        match want {
            Some(r) => {
                let pad = cfg.thickness.clamp(1, 8) + 2;
                let need_w = r.w + pad * 2;
                let need_h = r.h + pad * 2;
                
                // Grow the surface in 64 px steps, never shrink: the surplus is fully
                // transparent (per-pixel alpha), so a surface larger than the frame is
                // invisible, and reallocating it constantly is what used to freeze the
                // overlay.
                let qw = (((need_w + 63) / 64) * 64).clamp(64, 8192);
                let qh = (((need_h + 63) / 64) * 64).clamp(64, 8192);
                if qw > win_w {
                    win_w = qw;
                }
                if qh > win_h {
                    win_h = qh;
                }
                let off_x = ((win_w - need_w) / 2).max(0);
                let off_y = ((win_h - need_h) / 2).max(0);
                
                let (wx, wy) = m.pt(r.x - pad - off_x, r.y - pad - off_y);
                let (ww, wh) = (win_w, win_h);
                let geom = (wx, wy, ww, wh);
                
                let moved = match last_geom {
                    Some(g) => {
                        (g.0 - wx).abs() > 2 || (g.1 - wy).abs() > 2
                            || (g.2 - ww).abs() > 2 || (g.3 - wh).abs() > 2
                    }
                    None => true,
                };
                let dragging = unsafe {
                    use windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;
                    (GetAsyncKeyState(0x01) as u16 & 0x8000) != 0
                };
                let due = !dragging && last_move.elapsed() >= std::time::Duration::from_millis(70);
                
                let key = (ww, wh, off_x, off_y, cfg.thickness, cfg.show_label, cfg.brackets, label.clone());
                let stale = surf.as_ref().map(|s| (s.w, s.h) != (ww, wh)).unwrap_or(true);
                if stale {
                    surf = Surface::new(ww, wh);
                    if surf.is_none() {
                        crate::mc_warn!("hud", "could not allocate a {}x{} surface", ww, wh);
                    }
                }
                if let Some(s) = surf.as_mut() {
                    if (moved || last_paint_key.as_ref() != Some(&key)) && due {
                        let fx = off_x + pad;
                        let fy = off_y + pad;
                        if paint(hwnd, s, wx, wy, &label, cfg, Some((fx, fy, r.w, r.h))) {
                            last_paint_key = Some(key);
                            last_geom = Some(geom);
                            last_move = std::time::Instant::now();
                            crate::mc_debug!("hud", "overlay at {},{} {}x{} frame {}x{}", wx, wy, ww, wh, r.w, r.h);
                        } else {
                            crate::mc_debug!("hud", "UpdateLayeredWindow failed, retrying");
                        }
                    }
                }
                if surf.is_some() {
                    if !shown || !IsWindowVisible(hwnd).as_bool() {
                        let _ = ShowWindow(hwnd, SW_SHOWNOACTIVATE);
                        shown = true;
                    }
                    if !capturable {
                        let _ = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);
                    }
                }
            }

            None => {
                if shown {
                    let _ = ShowWindow(hwnd, SW_HIDE);
                    shown = false;
                    last_geom = None;
                    last_paint_key = None;
                }
            }
        }

        // No message pump: this window never handles input, and pumping here
        // used to re-enter paint() and stall the thread on the state lock.
        std::thread::sleep(std::time::Duration::from_millis(33));
    }

    let _ = ShowWindow(hwnd, SW_HIDE);
    // Tear the window down: start() can be called again, and an orphaned window
    // from a dead thread keeps drawing stale pixels over the desktop.
    let _ = windows::Win32::UI::WindowsAndMessaging::DestroyWindow(hwnd);
    let hinst = GetModuleHandleW(None).unwrap_or_default();
    let _ = windows::Win32::UI::WindowsAndMessaging::UnregisterClassW(w!("MouseCamHud"), Some(hinst.into()));
    STARTED.store(false, Ordering::SeqCst);
}
// ---------------------------------------------------------------- surface
//
// The overlay owns a 32-bit ARGB bitmap and hands it to the compositor with
// UpdateLayeredWindow. The previous version used LWA_COLORKEY and painted
// through the window DC: a colour key needs the window to be repainted, and a
// window whose thread has no message pump is never repainted, so any surface
// the system recreated (a resize, a display change) stayed opaque black. With
// ULW the pixels are always exactly what we produced - a black overlay is not
// representable.

pub(crate) struct Surface {
    dc: windows::Win32::Graphics::Gdi::HDC,
    bmp: windows::Win32::Graphics::Gdi::HBITMAP,
    old: windows::Win32::Graphics::Gdi::HGDIOBJ,
    bits: *mut u32,
    pub(crate) w: i32,
    pub(crate) h: i32,
}

impl Surface {
    pub(crate) unsafe fn new(w: i32, h: i32) -> Option<Surface> {
        use windows::Win32::Graphics::Gdi::{
            CreateCompatibleDC, CreateDIBSection, SelectObject, BITMAPINFO, BITMAPINFOHEADER,
            BI_RGB, DIB_RGB_COLORS,
        };
        let dc = CreateCompatibleDC(None);
        if dc.is_invalid() {
            return None;
        }
        let mut bi = BITMAPINFO::default();
        bi.bmiHeader.biSize = std::mem::size_of::<BITMAPINFOHEADER>() as u32;
        bi.bmiHeader.biWidth = w;
        bi.bmiHeader.biHeight = -h; // top-down
        bi.bmiHeader.biPlanes = 1;
        bi.bmiHeader.biBitCount = 32;
        bi.bmiHeader.biCompression = BI_RGB.0;
        let mut bits: *mut std::ffi::c_void = std::ptr::null_mut();
        let bmp = match CreateDIBSection(Some(dc), &bi, DIB_RGB_COLORS, &mut bits, None, 0) {
            Ok(b) => b,
            Err(_) => {
                let _ = windows::Win32::Graphics::Gdi::DeleteDC(dc);
                return None;
            }
        };
        if bits.is_null() {
            let _ = windows::Win32::Graphics::Gdi::DeleteObject(windows::Win32::Graphics::Gdi::HGDIOBJ(bmp.0));
            let _ = windows::Win32::Graphics::Gdi::DeleteDC(dc);
            return None;
        }
        let old = SelectObject(dc, windows::Win32::Graphics::Gdi::HGDIOBJ(bmp.0));
        Some(Surface { dc, bmp, old, bits: bits as *mut u32, w, h })
    }
}

impl Drop for Surface {
    fn drop(&mut self) {
        unsafe {
            use windows::Win32::Graphics::Gdi::{DeleteDC, DeleteObject, SelectObject};
            if !self.old.is_invalid() {
                SelectObject(self.dc, self.old);
            }
            let _ = DeleteObject(windows::Win32::Graphics::Gdi::HGDIOBJ(self.bmp.0));
            let _ = DeleteDC(self.dc);
        }
    }
}

/// Draws the frame into the surface and pushes it to the compositor, which also
/// positions and sizes the window - one call, no SetWindowPos.
pub(crate) unsafe fn paint(
    hwnd: windows::Win32::Foundation::HWND,
    surf: &mut Surface,
    wx: i32,
    wy: i32,
    label: &str,
    cfg: HudConfig,
    rect: Option<(i32, i32, i32, i32)>,
) -> bool {
    use windows::Win32::Foundation::{COLORREF, POINT, RECT, SIZE};
    use windows::Win32::Graphics::Gdi::{
        CreateSolidBrush, DeleteObject, FillRect, SetBkMode, SetTextColor, TextOutW, AC_SRC_ALPHA,
        AC_SRC_OVER, BLENDFUNCTION, TRANSPARENT,
    };
    use windows::Win32::UI::WindowsAndMessaging::{UpdateLayeredWindow, ULW_ALPHA};

    let accent = COLORREF(0x00FF_8C4F); // #4f8cff, COLORREF is 0x00BBGGRR
    let dark = COLORREF(0x0010_0C0A);

    let (w, h) = (surf.w, surf.h);
    if w <= 0 || h <= 0 {
        return false;
    }
    let dc = surf.dc;

    // transparent background
    std::ptr::write_bytes(surf.bits, 0, (w * h) as usize);

    let _ = SetBkMode(dc, TRANSPARENT);

    let pad = cfg.thickness.clamp(1, 8) + 2;
    let (rx, ry, rw, rh) = match rect {
        Some(v) => v,
        None => (pad, pad, (w - pad * 2).max(2), (h - pad * 2).max(2)),
    };

    let t = cfg.thickness.clamp(1, 8);

    let hb = CreateSolidBrush(accent);
    for b in [
        RECT { left: rx, top: ry, right: rx + rw, bottom: ry + t },
        RECT { left: rx, top: ry + rh - t, right: rx + rw, bottom: ry + rh },
        RECT { left: rx, top: ry, right: rx + t, bottom: ry + rh },
        RECT { left: rx + rw - t, top: ry, right: rx + rw, bottom: ry + rh },
    ] {
        FillRect(dc, &b, hb);
    }
    let _ = DeleteObject(hb.into());

    if cfg.brackets {
        let cw = (rw / 6).clamp(10, 30);
        let ch = (rh / 6).clamp(10, 30);
        let bt = (t + 2).min(7);
        let vb = CreateSolidBrush(accent);
        for (x, y) in [
            (rx, ry),
            (rx + rw - cw, ry),
            (rx, ry + rh - bt),
            (rx + rw - cw, ry + rh - bt),
        ] {
            FillRect(dc, &RECT { left: x, top: y, right: x + cw, bottom: y + bt }, vb);
        }
        for (x, y) in [
            (rx, ry),
            (rx + rw - bt, ry),
            (rx, ry + rh - ch),
            (rx + rw - bt, ry + rh - ch),
        ] {
            FillRect(dc, &RECT { left: x, top: y, right: x + bt, bottom: y + ch }, vb);
        }
        let _ = DeleteObject(vb.into());
    }

    if cfg.show_label && !label.is_empty() {
        let wide: Vec<u16> = label.encode_utf16().collect();
        let lp = 8;
        let bw = (wide.len() as i32) * 7 + 12;
        let bh = 18;
        let boxr = RECT {
            left: rx + lp,
            top: ry + lp,
            right: rx + lp + bw,
            bottom: ry + lp + bh,
        };
        let bg = CreateSolidBrush(accent);
        let _ = FillRect(dc, &boxr, bg);
        let _ = DeleteObject(bg.into());
        let _ = SetTextColor(dc, dark);
        let _ = TextOutW(dc, rx + lp + 6, ry + lp + 3, &wide);
    }

    // GDI writes colour but never alpha, so anything it touched becomes opaque;
    // the untouched background keeps alpha 0 and stays transparent.
    let px = std::slice::from_raw_parts_mut(surf.bits, (w * h) as usize);
    for p in px.iter_mut() {
        if *p & 0x00FF_FFFF != 0 {
            *p |= 0xFF00_0000;
        }
    }

    let blend = BLENDFUNCTION {
        BlendOp: AC_SRC_OVER as u8,
        BlendFlags: 0,
        SourceConstantAlpha: 255,
        AlphaFormat: AC_SRC_ALPHA as u8,
    };
    let pt_dst = POINT { x: wx, y: wy };
    let size = SIZE { cx: w, cy: h };
    let pt_src = POINT { x: 0, y: 0 };
    UpdateLayeredWindow(hwnd, None, Some(&pt_dst), Some(&size), Some(dc), Some(&pt_src), COLORREF(0), Some(&blend), ULW_ALPHA).is_ok()
}

