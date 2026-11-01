//! Edit list (`.mcl`): trims, manual follow-point keyframes and camera
//! parameters. Line based on purpose so the UI and a human edit the same text.

use crate::settings::Settings;
use crate::track::TrackPt;

/// `< 0` means "keep whatever meta.json says".
#[derive(Clone, Copy, Debug)]
pub struct RenderOpts {
    pub zoom: f32,
    pub expand: f32,
    pub threshold: f32,
    pub smooth: f32,
    pub resp: f32,
    pub follow: f32,
    pub look: f32,
    pub aspect: i32,
    pub width: i32,
    pub fps: i32,
}

impl Default for RenderOpts {
    fn default() -> Self {
        Self {
            zoom: -1.0,
            expand: -1.0,
            threshold: -1.0,
            smooth: -1.0,
            resp: -1.0,
            follow: -1.0,
            look: -1.0,
            aspect: -1,
            width: -1,
            fps: -1,
        }
    }
}

impl RenderOpts {
    pub fn apply(&self, s: &mut Settings) {
        if self.zoom > 0.0 {
            s.zoom = self.zoom;
        }
        if self.expand > 0.0 {
            s.speed_expand = self.expand;
        }
        if self.threshold > 0.0 {
            s.speed_threshold = self.threshold;
        }
        if self.smooth >= 0.0 {
            s.smooth = self.smooth;
        }
        if self.resp >= 0.0 {
            s.speed_resp = self.resp;
        }
        if self.follow > 0.0 {
            s.follow_hz = self.follow;
        }
        if self.look >= 0.0 {
            s.lookahead_ms = self.look;
        }
        if self.aspect >= 0 && (self.aspect as usize) < crate::settings::ASPECTS.len() {
            s.aspect_idx = self.aspect as usize;
        }
        if self.width > 0 {
            s.out_width = self.width;
        }
        if self.fps > 0 {
            s.fps = self.fps;
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct EditList {
    pub trims: Vec<(f64, f64)>,
    pub kf: Vec<TrackPt>,
    pub cam: RenderOpts,
}

pub fn parse_edit(text: &str) -> EditList {
    let mut e = EditList::default();

    for raw in text.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let mut parts = line.splitn(2, |c: char| c.is_whitespace());
        let key = parts.next().unwrap_or("").to_ascii_lowercase();
        let rest = parts.next().unwrap_or("").trim();
        if rest.starts_with('#') {
            continue;
        }

        match key.as_str() {
            "trim" => {
                let v: Vec<f64> = rest
                    .split_whitespace()
                    .filter_map(|t| t.parse().ok())
                    .collect();
                if v.len() >= 2 && v[1] > v[0] {
                    e.trims.push((v[0], v[1]));
                }
            }
            "kf" => {
                let v: Vec<f64> = rest
                    .split_whitespace()
                    .filter_map(|t| t.parse().ok())
                    .collect();
                if v.len() >= 3 {
                    e.kf.push(TrackPt {
                        t: v[0].max(0.0),
                        x: v[1] as i32,
                        y: v[2] as i32,
                        btn: 0,
                    });
                }
            }
            "zoom" => e.cam.zoom = rest.parse().unwrap_or(e.cam.zoom),
            "expand" => e.cam.expand = rest.parse().unwrap_or(e.cam.expand),
            "threshold" => e.cam.threshold = rest.parse().unwrap_or(e.cam.threshold),
            "smooth" => e.cam.smooth = rest.parse().unwrap_or(e.cam.smooth),
            "resp" => e.cam.resp = rest.parse().unwrap_or(e.cam.resp),
            "follow" => e.cam.follow = rest.parse().unwrap_or(e.cam.follow),
            "look" => e.cam.look = rest.parse().unwrap_or(e.cam.look),
            "aspect" => e.cam.aspect = rest.parse().unwrap_or(e.cam.aspect),
            "width" => e.cam.width = rest.parse().unwrap_or(e.cam.width),
            "fps" => e.cam.fps = rest.parse().unwrap_or(e.cam.fps),
            _ => {}
        }
    }

    if e.kf.len() < 2 {
        e.kf.clear();
    }
    e.kf.sort_by(|a, b| a.t.partial_cmp(&b.t).unwrap_or(std::cmp::Ordering::Equal));
    e
}

/// Where the camera should aim: manual keyframes win inside their span.
pub fn cursor_at(track: &[TrackPt], edit: &EditList, t: f64) -> crate::camera::Vec2 {
    if edit.kf.len() >= 2 {
        let k = &edit.kf;
        if t >= k[0].t && t <= k[k.len() - 1].t {
            for i in 0..k.len() - 1 {
                if t >= k[i].t && t <= k[i + 1].t {
                    let span = k[i + 1].t - k[i].t;
                    let f = if span > 1e-9 {
                        (t - k[i].t) / span
                    } else {
                        0.0
                    };
                    return crate::camera::Vec2::new(
                        (k[i].x as f64 + (k[i + 1].x - k[i].x) as f64 * f) as f32,
                        (k[i].y as f64 + (k[i + 1].y - k[i].y) as f64 * f) as f32,
                    );
                }
            }
        }
    }
    crate::track::at(track, t)
}

/// output frame index -> source frame index, honouring the trims
pub fn build_frame_map(frame_count: i32, fps: i32, edit: &EditList) -> Vec<i32> {
    if edit.trims.is_empty() {
        return (0..frame_count).collect();
    }
    let mut map: Vec<i32> = Vec::new();
    for (a, b) in &edit.trims {
        let start = ((a * fps as f64).floor() as i32).max(0);
        let end = ((b * fps as f64).ceil() as i32).min(frame_count);
        for i in start..end {
            if map.last().map_or(true, |&last| i > last) {
                map.push(i);
            }
        }
    }
    map
}
