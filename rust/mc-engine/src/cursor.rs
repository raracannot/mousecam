//! System cursor sprite decoding (GDI) and scaled alpha compositing.

use windows::Win32::Foundation::HWND;
use windows::Win32::Graphics::Gdi::{
    DeleteObject, GetDC, GetDIBits, GetObjectW, ReleaseDC, BITMAP, BITMAPINFO, BITMAPINFOHEADER,
    BI_RGB, DIB_RGB_COLORS, HBITMAP, HDC, HGDIOBJ,
};
use windows::Win32::UI::WindowsAndMessaging::{
    GetCursorInfo, GetIconInfo, LoadCursorW, CURSORINFO, CURSOR_SHOWING, HCURSOR, HICON, ICONINFO,
    IDC_ARROW,
};

pub struct Sprite {
    pub w: i32,
    pub h: i32,
    pub hx: f32,
    pub hy: f32,
    /// straight (non-premultiplied) BGRA
    pub px: Vec<u32>,
}

fn dib_bits(hbm: HBITMAP, w: i32, h: i32) -> Option<Vec<u32>> {
    let mut bi = BITMAPINFO::default();
    bi.bmiHeader = BITMAPINFOHEADER {
        biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
        biWidth: w,
        biHeight: -h, // top-down
        biPlanes: 1,
        biBitCount: 32,
        biCompression: BI_RGB.0,
        ..Default::default()
    };

    let mut buf = vec![0u32; (w * h) as usize];
    unsafe {
        let dc: HDC = GetDC(None);
        let got = GetDIBits(
            dc,
            hbm,
            0,
            h as u32,
            Some(buf.as_mut_ptr() as *mut core::ffi::c_void),
            &mut bi,
            DIB_RGB_COLORS,
        );
        ReleaseDC(None, dc);
        if got == 0 {
            return None;
        }
    }
    Some(buf)
}

pub fn build_sprite(cur: HCURSOR) -> Option<Sprite> {
    if cur.0.is_null() {
        return None;
    }
    unsafe {
        let mut ii = ICONINFO::default();
        if GetIconInfo(HICON(cur.0), &mut ii).is_err() {
            return None;
        }
        // monochrome / mask-only cursors are skipped by the caller
        if ii.hbmColor.0.is_null() {
            if !ii.hbmMask.0.is_null() {
                let _ = DeleteObject(HGDIOBJ(ii.hbmMask.0));
            }
            return None;
        }

        let mut bm = BITMAP::default();
        let n = GetObjectW(
            HGDIOBJ(ii.hbmColor.0),
            std::mem::size_of::<BITMAP>() as i32,
            Some(&mut bm as *mut _ as *mut core::ffi::c_void),
        );
        if n == 0 || bm.bmWidth <= 0 || bm.bmHeight <= 0 || bm.bmWidth > 256 || bm.bmHeight > 256
        {
            let _ = DeleteObject(HGDIOBJ(ii.hbmColor.0));
            if !ii.hbmMask.0.is_null() {
                let _ = DeleteObject(HGDIOBJ(ii.hbmMask.0));
            }
            return None;
        }
        let (w, h) = (bm.bmWidth, bm.bmHeight);

        let color = dib_bits(ii.hbmColor, w, h);
        let mask = if ii.hbmMask.0.is_null() {
            None
        } else {
            dib_bits(ii.hbmMask, w, h)
        };

        let _ = DeleteObject(HGDIOBJ(ii.hbmColor.0));
        if !ii.hbmMask.0.is_null() {
            let _ = DeleteObject(HGDIOBJ(ii.hbmMask.0));
        }

        let mut col = color?;
        let any_alpha = col.iter().any(|c| (c >> 24) != 0);

        for (i, c) in col.iter_mut().enumerate() {
            let a = if any_alpha {
                (*c >> 24) & 0xFF
            } else {
                // legacy 1-bit mask: 0 = opaque
                match &mask {
                    Some(m) => {
                        if (m[i] & 0xFF) != 0 {
                            0
                        } else {
                            255
                        }
                    }
                    None => 255,
                }
            };
            if a == 0 {
                *c = 0;
            } else {
                *c = (a << 24) | (*c & 0x00FF_FFFF);
            }
        }

        Some(Sprite {
            w,
            h,
            hx: ii.xHotspot as f32,
            hy: ii.yHotspot as f32,
            px: col,
        })
    }
}

/// The standard arrow, used when re-rendering (the original shape is not recorded).
pub fn arrow_sprite() -> Option<Sprite> {
    unsafe {
        let cur: HCURSOR = LoadCursorW(None, IDC_ARROW).ok()?;
        build_sprite(cur)
    }
}

/// The cursor currently on screen, or None when hidden.
pub fn current_sprite() -> Option<Sprite> {
    unsafe {
        let mut ci = CURSORINFO {
            cbSize: std::mem::size_of::<CURSORINFO>() as u32,
            ..Default::default()
        };
        if GetCursorInfo(&mut ci).is_err() {
            return None;
        }
        if (ci.flags.0 & CURSOR_SHOWING.0) == 0 {
            return None;
        }
        build_sprite(ci.hCursor)
    }
}

/// Bilinear scaled alpha blend of the sprite into a BGRA frame.
pub fn draw(dst: &mut [u32], dw: i32, dh: i32, cx: f32, cy: f32, scale: f32, spr: &Sprite) {
    if spr.w <= 0 || spr.h <= 0 || scale <= 0.0 {
        return;
    }
    let sx = spr.w as f32 * scale;
    let sy = spr.h as f32 * scale;
    let ox = cx - spr.hx * scale;
    let oy = cy - spr.hy * scale;

    let mut x0 = ox.floor() as i32;
    let mut y0 = oy.floor() as i32;
    let mut x1 = (ox + sx).ceil() as i32;
    let mut y1 = (oy + sy).ceil() as i32;
    if x1 <= 0 || y1 <= 0 || x0 >= dw || y0 >= dh {
        return;
    }
    x0 = x0.max(0);
    y0 = y0.max(0);
    x1 = x1.min(dw);
    y1 = y1.min(dh);

    let sw = spr.w;
    for y in y0..y1 {
        let v = (y as f32 + 0.5 - oy) / scale;
        // clamp the sampled index for p00/p01, but derive ix1/iy1 from the
        // UNCLAMPED index - matching the reference build exactly at the edges
        let iy_raw = v.floor() as i32;
        let fy = v - iy_raw as f32;
        let iy = iy_raw.clamp(0, spr.h - 1) as usize;
        let iy1 = (iy_raw + 1).clamp(0, spr.h - 1) as usize;

        for x in x0..x1 {
            let u = (x as f32 + 0.5 - ox) / scale;
            let ix_raw = u.floor() as i32;
            let fx = u - ix_raw as f32;
            let ix = ix_raw.clamp(0, spr.w - 1) as usize;
            let ix1 = (ix_raw + 1).clamp(0, spr.w - 1) as usize;

            let row0 = iy * sw as usize;
            let row1 = iy1 * sw as usize;
            let p00 = spr.px[row0 + ix];
            let p10 = spr.px[row0 + ix1];
            let p01 = spr.px[row1 + ix];
            let p11 = spr.px[row1 + ix1];

            let a00 = ((p00 >> 24) & 0xFF) as f32 * (1.0 - fx) * (1.0 - fy);
            let a10 = ((p10 >> 24) & 0xFF) as f32 * fx * (1.0 - fy);
            let a01 = ((p01 >> 24) & 0xFF) as f32 * (1.0 - fx) * fy;
            let a11 = ((p11 >> 24) & 0xFF) as f32 * fx * fy;
            let asum = a00 + a10 + a01 + a11;
            if asum < 1.0 {
                continue;
            }
            let af = (asum / 255.0).min(1.0);

            let ch = |shift: u32| -> f32 {
                (((p00 >> shift) & 0xFF) as f32 * a00
                    + ((p10 >> shift) & 0xFF) as f32 * a10
                    + ((p01 >> shift) & 0xFF) as f32 * a01
                    + ((p11 >> shift) & 0xFF) as f32 * a11)
                    / asum
            };
            let (r, g, b) = (ch(16), ch(8), ch(0));

            let d = &mut dst[(y * dw + x) as usize];
            let dc = *d;
            let dr = ((dc >> 16) & 0xFF) as f32;
            let dg = ((dc >> 8) & 0xFF) as f32;
            let db = (dc & 0xFF) as f32;

            let rr = (dr + (r - dr) * af) as u32;
            let gg = (dg + (g - dg) * af) as u32;
            let bb = (db + (b - db) * af) as u32;
            *d = 0xFF00_0000 | (rr.min(255) << 16) | (gg.min(255) << 8) | bb.min(255);
        }
    }
}

/// Compose the live cursor (used by the live recorder path later).
pub fn draw_current(dst: &mut [u32], dw: i32, dh: i32, cx: f32, cy: f32, scale: f32) {
    if let Some(spr) = current_sprite() {
        draw(dst, dw, dh, cx, cy, scale, &spr);
    }
}

/// Keep the facade honest: a hidden cursor must draw nothing.
pub fn cursor_visible() -> bool {
    unsafe {
        let mut ci = CURSORINFO {
            cbSize: std::mem::size_of::<CURSORINFO>() as u32,
            ..Default::default()
        };
        if GetCursorInfo(&mut ci).is_err() {
            return false;
        }
        (ci.flags.0 & CURSOR_SHOWING.0) != 0
    }
}

/// Silence unused-import warnings on non-Windows targets during docs builds.
#[allow(dead_code)]
fn _assert_hwnd(_: Option<HWND>) {}

/// Rebuilds the sprite only when the cursor shape actually changes.
pub struct SpriteCache {
    handle: isize,
    spr: Option<Sprite>,
}

impl Default for SpriteCache {
    fn default() -> Self {
        Self::new()
    }
}

impl SpriteCache {
    pub fn new() -> Self {
        Self {
            handle: 0,
            spr: None,
        }
    }

    /// None when the cursor is hidden.
    pub fn get(&mut self) -> Option<&Sprite> {
        unsafe {
            let mut ci = CURSORINFO {
                cbSize: std::mem::size_of::<CURSORINFO>() as u32,
                ..Default::default()
            };
            if GetCursorInfo(&mut ci).is_err() {
                return None;
            }
            if (ci.flags.0 & CURSOR_SHOWING.0) == 0 {
                return None;
            }
            let h = ci.hCursor.0 as isize;
            if h != self.handle || self.spr.is_none() {
                self.handle = h;
                self.spr = build_sprite(ci.hCursor);
            }
            self.spr.as_ref()
        }
    }
}
