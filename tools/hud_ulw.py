import io

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
src = io.open(p, encoding="utf-8").read()
lines = src.split("\n")

# ---------------------------------------------------------------- 1. replace paint
i = next(i for i, l in enumerate(lines) if l.startswith("unsafe fn paint("))
head = "\n".join(lines[:i])

new_paint = r'''// ---------------------------------------------------------------- surface
//
// The overlay owns a 32-bit ARGB bitmap and hands it to the compositor with
// UpdateLayeredWindow. The previous version used LWA_COLORKEY and painted
// through the window DC: a colour key needs the window to be repainted, and a
// window whose thread has no message pump is never repainted, so any surface
// the system recreated (a resize, a display change) stayed opaque black. With
// ULW the pixels are always exactly what we produced - a black overlay is not
// representable.

struct Surface {
    dc: HDC,
    bmp: HBITMAP,
    old: HGDIOBJ,
    bits: *mut u32,
    w: i32,
    h: i32,
}

impl Surface {
    unsafe fn new(w: i32, h: i32) -> Option<Surface> {
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
            let _ = windows::Win32::Graphics::Gdi::DeleteObject(bmp);
            let _ = windows::Win32::Graphics::Gdi::DeleteDC(dc);
            return None;
        }
        let old = SelectObject(dc, bmp);
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
            let _ = DeleteObject(self.bmp);
            let _ = DeleteDC(self.dc);
        }
    }
}

/// Draws the frame into the surface and pushes it to the compositor, which also
/// positions and sizes the window - one call, no SetWindowPos.
unsafe fn paint(
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
'''

io.open(p, "w", encoding="utf-8", newline="").write(head + new_paint + "\n")
print("paint replaced with the UpdateLayeredWindow version")
