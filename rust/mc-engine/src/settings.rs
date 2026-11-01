//! Recording / re-render parameters. Mirrors the C++ `Settings` subset that the
//! offline renderer needs.

pub const ASPECTS: [(&str, f32); 6] = [
    ("16:9", 16.0 / 9.0),
    ("9:16", 9.0 / 16.0),
    ("1:1", 1.0),
    ("4:3", 4.0 / 3.0),
    ("21:9", 21.0 / 9.0),
    ("3:2", 3.0 / 2.0),
];

pub fn aspect_value(idx: usize) -> f32 {
    ASPECTS.get(idx).map(|a| a.1).unwrap_or(ASPECTS[0].1)
}

#[derive(Clone, Debug)]
pub struct Settings {
    pub fps: i32,
    pub out_width: i32,
    pub aspect_idx: usize,
    pub zoom: f32,
    pub speed_expand: f32,
    pub speed_threshold: f32,
    pub smooth: f32,
    pub speed_resp: f32,
    pub follow_hz: f32,
    pub lookahead_ms: f32,
    pub clamp_to_screen: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            fps: 30,
            out_width: 1080,
            aspect_idx: 0,
            zoom: 1.0,
            speed_expand: 1.2,
            speed_threshold: 3400.0,
            smooth: 66.0,
            speed_resp: 35.0,
            follow_hz: 1.0,
            lookahead_ms: 60.0,
            clamp_to_screen: true,
        }
    }
}

impl Settings {
    /// Output height for the chosen aspect (always even).
    pub fn out_height(&self) -> i32 {
        let h = (self.out_width as f32 / aspect_value(self.aspect_idx)).round() as i32;
        h & !1
    }

    /// One Euro parameters derived from the two UI sliders.
    pub fn euro_params(&self) -> (f32, f32) {
        let t = (self.smooth / 100.0).clamp(0.0, 1.0);
        let min_cutoff = 10f32.powf(0.70 - 1.40 * t);
        let r = (self.speed_resp / 100.0).clamp(0.0, 1.0);
        let beta = (0.055 * r * r / 0.1225).max(0.0);
        (min_cutoff, beta)
    }
}
