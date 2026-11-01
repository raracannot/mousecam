//! Bilinear resampler with precomputed per-column / per-row integer weights.
//! Same arithmetic as the C++ version (weights 0..256, >>16 accumulate) so the
//! output is bit-comparable.

pub struct Resampler {
    dw: i32,
    dh: i32,
    direct: bool,
    dx: i32,
    dy: i32,
    x0: Vec<i32>,
    x1: Vec<i32>,
    wx0: Vec<i32>,
    wx1: Vec<i32>,
    y0: Vec<i32>,
    y1: Vec<i32>,
    wy0: Vec<i32>,
    wy1: Vec<i32>,
}

impl Default for Resampler {
    fn default() -> Self {
        Self::new()
    }
}

impl Resampler {
    pub fn new() -> Self {
        Self {
            dw: 0,
            dh: 0,
            direct: false,
            dx: 0,
            dy: 0,
            x0: Vec::new(),
            x1: Vec::new(),
            wx0: Vec::new(),
            wx1: Vec::new(),
            y0: Vec::new(),
            y1: Vec::new(),
            wy0: Vec::new(),
            wy1: Vec::new(),
        }
    }

    /// `sx, sy, sw, sh` describe the source window in source pixels.
    pub fn prep(&mut self, sx: f32, sy: f32, sw: f32, sh: f32, dw: i32, dh: i32) {
        self.dw = dw;
        self.dh = dh;

        let ix = sx.round() as i32;
        let iy = sy.round() as i32;
        self.direct = dw == sw.round() as i32
            && dh == sh.round() as i32
            && (sx - ix as f32).abs() < 0.01
            && (sy - iy as f32).abs() < 0.01;
        self.dx = ix;
        self.dy = iy;
        if self.direct {
            return;
        }

        let dwu = dw.max(1) as usize;
        let dhu = dh.max(1) as usize;
        self.x0.resize(dwu, 0);
        self.x1.resize(dwu, 0);
        self.wx0.resize(dwu, 0);
        self.wx1.resize(dwu, 0);
        self.y0.resize(dhu, 0);
        self.y1.resize(dhu, 0);
        self.wy0.resize(dhu, 0);
        self.wy1.resize(dhu, 0);

        let kx = sw / dw as f32;
        for x in 0..dwu {
            let s = sx + (x as f32 + 0.5) * kx - 0.5;
            let i = s.floor();
            let f = s - i;
            self.x0[x] = i as i32;
            self.x1[x] = i as i32 + 1;
            let w1 = (f * 256.0 + 0.5) as i32;
            self.wx1[x] = w1;
            self.wx0[x] = 256 - w1;
        }
        let ky = sh / dh as f32;
        for y in 0..dhu {
            let s = sy + (y as f32 + 0.5) * ky - 0.5;
            let i = s.floor();
            let f = s - i;
            self.y0[y] = i as i32;
            self.y1[y] = i as i32 + 1;
            let w1 = (f * 256.0 + 0.5) as i32;
            self.wy1[y] = w1;
            self.wy0[y] = 256 - w1;
        }
    }

    /// `src` is the full frame (top-down BGRA as u32), `sstride` its row pitch in
    /// pixels. `dst` receives `dw * dh` pixels with pitch `dstride`.
    pub fn run(&self, src: &[u32], sstride: i32, sh: i32, dst: &mut [u32], dstride: i32) {
        let dw = self.dw;
        let dh = self.dh;
        if dw <= 0 || dh <= 0 {
            return;
        }
        let sw = sstride;

        if self.direct
            && self.dy >= 0
            && self.dy + dh <= sh
            && self.dx >= 0
            && self.dx + dw <= sw
        {
            for y in 0..dh {
                let s = ((self.dy + y) * sw + self.dx) as usize;
                let d = (y * dstride) as usize;
                dst[d..d + dw as usize].copy_from_slice(&src[s..s + dw as usize]);
            }
            return;
        }

        let maxx = (sw - 1).max(0);
        let maxy = (sh - 1).max(0);

        for y in 0..dh {
            let yu = y as usize;
            let ya = self.y0[yu].clamp(0, maxy);
            let yb = self.y1[yu].clamp(0, maxy);
            let wa0 = self.wy0[yu];
            let wa1 = self.wy1[yu];
            let r0 = (ya * sw) as usize;
            let r1 = (yb * sw) as usize;
            let drow = (y * dstride) as usize;

            for x in 0..dw {
                let xu = x as usize;
                let xa = self.x0[xu].clamp(0, maxx) as usize;
                let xb = self.x1[xu].clamp(0, maxx) as usize;
                let bx = self.wx0[xu];
                let by = self.wx1[xu];

                let p00 = src[r0 + xa];
                let p10 = src[r0 + xb];
                let p01 = src[r1 + xa];
                let p11 = src[r1 + xb];

                let ch = |sh: u32| -> i32 {
                    ((p00 >> sh) & 0xFF) as i32 * bx * wa0
                        + ((p10 >> sh) & 0xFF) as i32 * by * wa0
                        + ((p01 >> sh) & 0xFF) as i32 * bx * wa1
                        + ((p11 >> sh) & 0xFF) as i32 * by * wa1
                };

                let b = (ch(0) >> 16).clamp(0, 255) as u32;
                let g = (ch(8) >> 16).clamp(0, 255) as u32;
                let r = (ch(16) >> 16).clamp(0, 255) as u32;
                dst[drow + xu] = 0xFF00_0000 | (r << 16) | (g << 8) | b;
            }
        }
    }
}
