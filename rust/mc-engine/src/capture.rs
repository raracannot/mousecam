//! Screen capture: DXGI Desktop Duplication with a GDI BitBlt fallback.
//!
//! This is the only module that concentrates `unsafe`: COM vtable calls and
//! GDI handles. Everything above it works on plain `&mut [u32]` buffers.

use crate::camera::IRect;
use windows::core::Interface;
use windows::Win32::Foundation::{HMODULE, RECT};
use windows::Win32::Graphics::Direct3D::{
    D3D_DRIVER_TYPE_UNKNOWN, D3D_FEATURE_LEVEL_10_0, D3D_FEATURE_LEVEL_11_0,
};
use windows::Win32::Graphics::Direct3D11::{
    D3D11CreateDevice, ID3D11Device, ID3D11DeviceContext, ID3D11Texture2D, D3D11_CPU_ACCESS_READ,
    D3D11_CREATE_DEVICE_FLAG, D3D11_MAP_READ, D3D11_MAPPED_SUBRESOURCE, D3D11_SDK_VERSION,
    D3D11_TEXTURE2D_DESC, D3D11_USAGE_STAGING,
};
use windows::Win32::Graphics::Dxgi::Common::{DXGI_FORMAT_B8G8R8A8_UNORM, DXGI_SAMPLE_DESC};
use windows::Win32::Graphics::Dxgi::{
    CreateDXGIFactory1, IDXGIFactory1, IDXGIOutput1, IDXGIOutputDuplication, IDXGIResource,
    DXGI_ERROR_WAIT_TIMEOUT, DXGI_OUTDUPL_FRAME_INFO,
};
use windows::Win32::Graphics::Gdi::{
    BitBlt, CreateCompatibleDC, CreateDIBSection, DeleteDC, DeleteObject, GetDC, ReleaseDC,
    SelectObject, BITMAPINFO, BITMAPINFOHEADER, BI_RGB, DIB_RGB_COLORS, HBITMAP, HDC, HGDIOBJ,
    SRCCOPY,
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CapturePath {
    /// GPU duplication: ~2-5 ms at 1440p
    Duplication,
    /// GDI fallback: 25-40 ms at 1440p, used in RDP / VMs / when another
    /// duplicator already owns the output
    BitBlt,
}

/// Field order matters: Rust drops fields in declaration order, and releasing
/// the device before its children makes their Release() walk a dead object.
/// Dependents first, device last.
struct Dda {
    /// Set when the duplication died (display change, UAC, a fullscreen
    /// app taking the output). The owner reopens instead of failing forever.
    lost: bool,
    /// The surface no longer matches the monitor rect, so the previous frame is
    /// only partially filled. The owner should reopen the capture.
    resized: bool,
    /// Set when the desktop handed us a surface we cannot map - HDR / 10-bit
    /// displays return R16G16B16A16_FLOAT. Silently returning the previous
    /// frame would record a frozen picture for the whole session.
    unsupported_format: Option<u32>,
    staging: ID3D11Texture2D,
    dup: IDXGIOutputDuplication,
    /// size of the duplication surface. For a rotated display this is the
    /// panel's own orientation, which is NOT the monitor rect (a 1080x1920
    /// portrait screen reports a 1920x1080 surface).
    scr_w: u32,
    scr_h: u32,
    rot: i32,
    context: ID3D11DeviceContext,
    device: ID3D11Device,
    have_frame: bool,
}

impl Dda {
    fn open(mon: IRect) -> Option<Self> {
        unsafe {
            let factory: IDXGIFactory1 = CreateDXGIFactory1().ok()?;
            let mut adapter = None;
            let mut output = None;

            let mut ai = 0u32;
            'outer: while let Ok(ad) = factory.EnumAdapters1(ai) {
                let mut oi = 0u32;
                while let Ok(out) = ad.EnumOutputs(oi) {
                    if let Ok(desc) = out.GetDesc() {
                        let r: RECT = desc.DesktopCoordinates;
                        if r.left == mon.x
                            && r.top == mon.y
                            && (r.right - r.left) == mon.w
                            && (r.bottom - r.top) == mon.h
                        {
                            adapter = Some(ad.clone());
                            output = Some(out);
                            break 'outer;
                        }
                    }
                    oi += 1;
                }
                ai += 1;
            }

            let adapter = adapter?;
            let output = output?;

            let adapter0: windows::Win32::Graphics::Dxgi::IDXGIAdapter = adapter.cast().ok()?;

            let levels = [D3D_FEATURE_LEVEL_11_0, D3D_FEATURE_LEVEL_10_0];
            let mut device: Option<ID3D11Device> = None;
            let mut context: Option<ID3D11DeviceContext> = None;
            let mut got = D3D_FEATURE_LEVEL_11_0;

            D3D11CreateDevice(
                Some(&adapter0),
                D3D_DRIVER_TYPE_UNKNOWN,
                HMODULE::default(),
                D3D11_CREATE_DEVICE_FLAG(0),
                Some(&levels),
                D3D11_SDK_VERSION,
                Some(&mut device),
                Some(&mut got),
                Some(&mut context),
            )
            .ok()?;

            let device = device?;
            let context = context?;

            let output1: IDXGIOutput1 = output.cast().ok()?;
            let dup = output1.DuplicateOutput(&device).ok()?;

            // Size the staging copy from the duplication surface. Using the
            // monitor rect here made CopyResource fail silently on rotated
            // displays, which showed up as a black preview.
            let od = dup.GetDesc();
            let scr_w = od.ModeDesc.Width.max(1);
            let scr_h = od.ModeDesc.Height.max(1);
            let rot = od.Rotation.0;

            let desc = D3D11_TEXTURE2D_DESC {
                Width: scr_w,
                Height: scr_h,
                MipLevels: 1,
                ArraySize: 1,
                Format: DXGI_FORMAT_B8G8R8A8_UNORM,
                SampleDesc: DXGI_SAMPLE_DESC {
                    Count: 1,
                    Quality: 0,
                },
                Usage: D3D11_USAGE_STAGING,
                BindFlags: 0,
                CPUAccessFlags: D3D11_CPU_ACCESS_READ.0 as u32,
                MiscFlags: 0,
            };
            let mut tex: Option<ID3D11Texture2D> = None;
            device.CreateTexture2D(&desc, None, Some(&mut tex)).ok()?;
            let staging = tex?;

            Some(Dda {
                staging,
                dup,
                scr_w,
                scr_h,
                rot,
                context,
                device,
                have_frame: false,
                lost: false,
                resized: false,
                unsupported_format: None,
            })
        }
    }

    fn grab(&mut self, dst: &mut [u32], w: i32, h: i32) -> bool {
        unsafe {
            let mut info = DXGI_OUTDUPL_FRAME_INFO::default();
            let mut res: Option<IDXGIResource> = None;

            match self.dup.AcquireNextFrame(0, &mut info, &mut res) {
                Ok(()) => {}
                Err(e) if e.code() == DXGI_ERROR_WAIT_TIMEOUT => return self.have_frame,
                // ACCESS_LOST / DEVICE_REMOVED: the duplication is dead and every later
                // call would fail too, so tell the owner to reopen it.
                Err(_) => {
                    self.lost = true;
                    return false;
                }
            }

            let mut copied = false;
            if let Some(res) = res {
                if let Ok(tex) = res.cast::<ID3D11Texture2D>() {
                    let mut d = D3D11_TEXTURE2D_DESC::default();
                    tex.GetDesc(&mut d);
                    if d.Format != DXGI_FORMAT_B8G8R8A8_UNORM {
                        if self.unsupported_format.is_none() {
                            self.unsupported_format = Some(d.Format.0 as u32);
                        }
                    }
                    if d.Format == DXGI_FORMAT_B8G8R8A8_UNORM {
                        // display mode changed (rotation, resolution): rebuild
                        if d.Width != self.scr_w || d.Height != self.scr_h {
                            let mut nd = D3D11_TEXTURE2D_DESC::default();
                            self.staging.GetDesc(&mut nd);
                            nd.Width = d.Width;
                            nd.Height = d.Height;
                            let mut nt: Option<ID3D11Texture2D> = None;
                            if self.device.CreateTexture2D(&nd, None, Some(&mut nt)).is_ok() {
                                if let Some(nt) = nt {
                                    self.staging = nt;
                                    self.scr_w = d.Width;
                                    self.scr_h = d.Height;
                                }
                            }
                        }
                        self.context.CopyResource(&self.staging, &tex);
                        copied = true;
                    }
                }
            }
            let _ = self.dup.ReleaseFrame();
            if !copied {
                return self.have_frame;
            }

            let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
            if self
                .context
                .Map(&self.staging, 0, D3D11_MAP_READ, 0, Some(&mut mapped))
                .is_err()
            {
                return false;
            }

            let pitch = mapped.RowPitch as usize;
            let src = mapped.pData as *const u8;

            // Rotated panel: the surface holds the panel orientation, the
            // caller wants the desktop orientation. Rotate while copying.
            // DXGI_MODE_ROTATION: 0 unspecified, 1 identity, 2/3/4 = 90/180/270
            // Only rotate when the request really is the desktop orientation of
            // this surface; otherwise a plain copy is the honest fallback.
            let rot_ok = match self.rot {
                2 | 4 => w == self.scr_h as i32 && h == self.scr_w as i32,
                3 => w == self.scr_w as i32 && h == self.scr_h as i32,
                _ => false,
            };
            if rot_ok {
                let sw = self.scr_w as usize;
                let sh = self.scr_h as usize;
                let dw = w as usize;
                let dh = h as usize;
                if dw * dh <= dst.len() && sw * sh > 0 {
                    let dptr = dst.as_mut_ptr() as *mut u8;
                    for dy in 0..dh {
                        for dx in 0..dw {
                            let (sx, sy) = match self.rot {
                                2 => (dy, sh - 1 - dx),        // ROTATE90
                                3 => (sw - 1 - dx, sh - 1 - dy), // ROTATE180
                                _ => (sw - 1 - dy, dx),          // ROTATE270
                            };
                            if sx < sw && sy < sh {
                                let s_off = sy * pitch + sx * 4;
                                let d_off = (dy * dw + dx) * 4;
                                std::ptr::copy_nonoverlapping(
                                    src.add(s_off),
                                    dptr.add(d_off),
                                    4,
                                );
                            }
                        }
                    }
                }
                self.context.Unmap(&self.staging, 0);
                self.have_frame = true;
                return true;
            }

            // The staging texture is rebuilt when the display changes size, but
            // `w`/`h` come from the monitor rect captured at open() time. If the
            // surface shrank, copying w*h from it reads past the mapping, so the
            // copy is clamped to the surface that was actually mapped.
            let copy_w = (w as usize).min(self.scr_w as usize).min(pitch / 4);
            let copy_h = (h as usize).min(self.scr_h as usize);
            let row_bytes = copy_w * 4;
            let dptr = dst.as_mut_ptr() as *mut u8;
            for y in 0..copy_h {
                std::ptr::copy_nonoverlapping(src.add(y * pitch), dptr.add(y * w as usize * 4), row_bytes);
            }
            if copy_w != w as usize || copy_h != h as usize {
                self.resized = true;
            }
            self.context.Unmap(&self.staging, 0);
            self.have_frame = true;
            let _ = self.device;
            true
        }
    }
}

struct BitbltCap {
    screen_dc: HDC,
    mem_dc: HDC,
    dib: HBITMAP,
    old: HGDIOBJ,
    bits: *mut u32,
}

impl BitbltCap {
    fn open(mon: IRect) -> Option<Self> {
        unsafe {
            let screen_dc = GetDC(None);
            if screen_dc.is_invalid() {
                return None;
            }
            let mem_dc = CreateCompatibleDC(Some(screen_dc));
            if mem_dc.is_invalid() {
                ReleaseDC(None, screen_dc);
                return None;
            }

            let bmi = BITMAPINFO {
                bmiHeader: BITMAPINFOHEADER {
                    biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
                    biWidth: mon.w,
                    biHeight: -mon.h, // top-down
                    biPlanes: 1,
                    biBitCount: 32,
                    biCompression: BI_RGB.0,
                    ..Default::default()
                },
                ..Default::default()
            };

            let mut bits: *mut core::ffi::c_void = std::ptr::null_mut();
            let dib = CreateDIBSection(
                Some(mem_dc),
                &bmi,
                DIB_RGB_COLORS,
                &mut bits,
                None,
                0,
            )
            .ok()?;
            if dib.is_invalid() || bits.is_null() {
                ReleaseDC(None, screen_dc);
                let _ = DeleteDC(mem_dc);
                return None;
            }
            let old = SelectObject(mem_dc, HGDIOBJ(dib.0));

            Some(BitbltCap {
                screen_dc,
                mem_dc,
                dib,
                old,
                bits: bits as *mut u32,
            })
        }
    }

    fn grab(&mut self, mon: IRect, w: i32, h: i32) -> bool {
        unsafe {
            if BitBlt(
                self.mem_dc,
                0,
                0,
                w,
                h,
                Some(self.screen_dc),
                mon.x,
                mon.y,
                SRCCOPY,
            )
            .is_err()
            {
                return false;
            }
            let _ = windows::Win32::Graphics::Gdi::GdiFlush();
            true
        }
    }
}

impl Drop for BitbltCap {
    fn drop(&mut self) {
        unsafe {
            if !self.old.is_invalid() {
                SelectObject(self.mem_dc, self.old);
            }
            if !self.dib.is_invalid() {
                let _ = DeleteObject(HGDIOBJ(self.dib.0));
            }
            if !self.mem_dc.is_invalid() {
                let _ = DeleteDC(self.mem_dc);
            }
            if !self.screen_dc.is_invalid() {
                ReleaseDC(None, self.screen_dc);
            }
        }
    }
}

// The BitBlt path owns a DIB section through raw pointers. `Capture` is moved
// wholesale into the recorder thread and never shared, so `Send` is sound here.
unsafe impl Send for BitbltCap {}
unsafe impl Send for Capture {}

pub struct Capture {
    mon: IRect,
    dda: Option<Dda>,
    blt: Option<BitbltCap>,
    pub path: CapturePath,
    pub fails: u32,
}

impl Capture {
    /// Tries GPU duplication first, falls back to GDI.
    pub fn open(mon: IRect) -> Result<Self, String> {
        if mon.w <= 0 || mon.h <= 0 {
            return Err("显示器矩形无效".into());
        }
        let mut cap = if let Some(dda) = Dda::open(mon) {
            Self {
                mon,
                dda: Some(dda),
                blt: None,
                path: CapturePath::Duplication,
                fails: 0,
            }
        } else if let Some(blt) = BitbltCap::open(mon) {
            Self {
                mon,
                dda: None,
                blt: Some(blt),
                path: CapturePath::BitBlt,
                fails: 0,
            }
        } else {
            return Err("无法初始化抓屏（DXGI 与 BitBlt 都失败）".into());
        };

        // A desktop running HDR or 10-bit colour hands back a surface we cannot
        // map. Refusing here is the only honest option: silencing it records a
        // frozen picture for the entire session.
        if cap.dda.is_some() {
            cap.probe_format(260);
            if let Some(code) = cap.format_problem() {
                return Err(format!(
                    "显示器色彩格式不支持（HDR 或 10bit，format=0x{code:X}）。请在 Windows 设置中关闭 HDR 后重试。"
                ));
            }
        }
        Ok(cap)
    }

    /// Grabs for up to `timeout_ms` looking for a surface format we cannot read.
    fn probe_format(&mut self, timeout_ms: u64) {
        let mut buf = vec![0u32; (self.mon.w as usize) * (self.mon.h as usize)];
        let deadline = std::time::Instant::now() + std::time::Duration::from_millis(timeout_ms);
        loop {
            self.grab(&mut buf);
            if self.format_problem().is_some() {
                return;
            }
            if self.dda.as_ref().map(|d| d.have_frame).unwrap_or(true) {
                return;
            }
            if std::time::Instant::now() >= deadline {
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(30));
        }
    }

    /// The surface format the desktop gave us, when it is one we cannot map.
    pub fn format_problem(&self) -> Option<u32> {
        self.dda.as_ref().and_then(|d| d.unsupported_format)
    }

    pub fn rect(&self) -> IRect {
        self.mon
    }

    /// Fills `dst` (monitor sized, top-down BGRA).
    pub fn grab(&mut self, dst: &mut [u32]) -> bool {
        let w = self.mon.w;
        let h = self.mon.h;
        let mon = self.mon;
        let ok = if let Some(dda) = self.dda.as_mut() {
            // Reopen the moment the duplication dies instead of waiting for 20
            // failed frames: until it is reopened the preview and the recording
            // both show a frozen picture and nobody can tell why.
            if dda.lost {
                crate::mc_warn!("capture", "duplication lost - reopening");
                match Dda::open(mon) {
                    Some(fresh) => {
                        *dda = fresh;
                        self.fails = 0;
                        crate::mc_info!("capture", "duplication reopened");
                    }
                    None => {
                        crate::mc_warn!("capture", "reopen failed, will retry next frame");
                    }
                }
                false
            } else {
                let r = dda.grab(dst, w, h);
                if !r {
                    self.fails += 1;
                    if self.fails > 20 {
                        self.fails = 0;
                        match Dda::open(mon) {
                            Some(fresh) => {
                                *dda = fresh;
                                crate::mc_warn!("capture", "duplication reopened after 20 failed frames");
                            }
                            None => {}
                        }
                    }
                } else {
                    self.fails = 0;
                }
                r
            }
        } else if let Some(blt) = self.blt.as_mut() {
            if !blt.grab(self.mon, w, h) {
                return false;
            }
            unsafe {
                std::ptr::copy_nonoverlapping(
                    blt.bits as *const u32,
                    dst.as_mut_ptr(),
                    (w as usize) * (h as usize),
                );
            }
            true
        } else {
            false
        };
        ok
    }
}

/// One physical display.
#[derive(Clone, Copy, Debug)]
pub struct MonitorInfo {
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
    pub primary: bool,
}

unsafe extern "system" fn collect_monitor(
    hmon: windows::Win32::Graphics::Gdi::HMONITOR,
    _hdc: windows::Win32::Graphics::Gdi::HDC,
    _rc: *mut windows::Win32::Foundation::RECT,
    data: windows::Win32::Foundation::LPARAM,
) -> windows::core::BOOL {
    use windows::Win32::Graphics::Gdi::{GetMonitorInfoW, MONITORINFO};
    let list = &mut *(data.0 as *mut Vec<MonitorInfo>);
    let mut mi = MONITORINFO {
        cbSize: std::mem::size_of::<MONITORINFO>() as u32,
        ..Default::default()
    };
    if GetMonitorInfoW(hmon, &mut mi).as_bool() {
        let r = mi.rcMonitor;
        list.push(MonitorInfo {
            x: r.left,
            y: r.top,
            w: r.right - r.left,
            h: r.bottom - r.top,
            primary: (mi.dwFlags & 1) != 0, // MONITORINFOF_PRIMARY
        });
    }
    windows::core::BOOL(1)
}

/// Every display, ordered left to right (then top to bottom) so "screen 1" is
/// always the leftmost, which is what people expect.
pub fn monitors() -> Vec<MonitorInfo> {
    use windows::Win32::Graphics::Gdi::EnumDisplayMonitors;
    let mut list: Vec<MonitorInfo> = Vec::new();
    unsafe {
        let _ = EnumDisplayMonitors(
            None,
            None,
            Some(collect_monitor),
            windows::Win32::Foundation::LPARAM(&mut list as *mut _ as isize),
        );
    }
    list.retain(|m| m.w > 0 && m.h > 0);
    list.sort_by_key(|m| (m.x, m.y));
    if list.is_empty() {
        // headless / RDP: fall back to the system metrics
        unsafe {
            use windows::Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN};
            list.push(MonitorInfo {
                x: 0,
                y: 0,
                w: GetSystemMetrics(SM_CXSCREEN),
                h: GetSystemMetrics(SM_CYSCREEN),
                primary: true,
            });
        }
    }
    list
}

/// Primary monitor rectangle in physical pixels.
pub fn primary_monitor_rect() -> IRect {
    let list = monitors();
    // monitors() guarantees at least one entry and never calls back into here
    let m = list
        .iter()
        .find(|m| m.primary)
        .copied()
        .unwrap_or(list[0]);
    IRect::new(m.x, m.y, m.w, m.h)
}
