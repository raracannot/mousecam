//! Recorded mouse trace: `track.csv` written by the recorder.

use crate::camera::Vec2;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

#[derive(Clone, Copy, Debug, Default)]
pub struct TrackPt {
    pub t: f64,
    pub x: i32,
    pub y: i32,
    pub btn: u32,
}

pub fn load_track(path: &Path) -> std::io::Result<Vec<TrackPt>> {
    let f = File::open(path)?;
    let mut out = Vec::new();
    for line in BufReader::new(f).lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };
        let l = line.trim();
        if l.is_empty() || l.starts_with('#') {
            continue;
        }
        let mut it = l.split(',');
        let t = match it.next().and_then(|v| v.parse::<f64>().ok()) {
            Some(v) => v,
            None => continue,
        };
        let x = it.next().and_then(|v| v.parse::<i32>().ok());
        let y = it.next().and_then(|v| v.parse::<i32>().ok());
        let b = it.next().and_then(|v| v.parse::<u32>().ok());
        if let (Some(x), Some(y)) = (x, y) {
            out.push(TrackPt { t, x, y, btn: b.unwrap_or(0) });
        }
    }
    Ok(out)
}

/// Linear interpolation between samples.
pub fn at(track: &[TrackPt], t: f64) -> Vec2 {
    if track.is_empty() {
        return Vec2::default();
    }
    let first = &track[0];
    let last = &track[track.len() - 1];
    if t <= first.t {
        return Vec2::new(first.x as f32, first.y as f32);
    }
    if t >= last.t {
        return Vec2::new(last.x as f32, last.y as f32);
    }

    let (mut lo, mut hi) = (0usize, track.len() - 1);
    while hi - lo > 1 {
        let mid = (lo + hi) / 2;
        if track[mid].t <= t {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    let span = track[hi].t - track[lo].t;
    let f = if span > 1e-9 {
        (t - track[lo].t) / span
    } else {
        0.0
    };
    Vec2::new(
        (track[lo].x as f64 + (track[hi].x - track[lo].x) as f64 * f) as f32,
        (track[lo].y as f64 + (track[hi].y - track[lo].y) as f64 * f) as f32,
    )
}
