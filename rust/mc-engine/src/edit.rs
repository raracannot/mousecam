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
    /// dead zone in percent of the viewport width; -1 keeps meta.json's value
    pub dz: f32,
    /// pointer smoothing in ms; -1 keeps meta.json's value
    pub cs: f32,
    /// click ring: -1 keeps meta.json's value, 0 off, 1 on
    pub clk: i32,
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
            dz: -1.0,
            cs: -1.0,
            clk: -1,
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
        if self.dz >= 0.0 {
            s.dead_zone = (self.dz / 100.0).clamp(0.0, 0.25);
        }
        if self.cs >= 0.0 {
            s.cursor_smooth_ms = self.cs.clamp(0.0, 250.0);
        }
        if self.clk >= 0 {
            s.click_ring = self.clk != 0;
        }
    }
}

/// A speed region: source seconds `[a, b]` play at `speed`.
///
/// `speed` is the playback rate, so 2.0 is a fast-forward and 0.5 is slow
/// motion. Regions are keyed on the *source* timeline so they survive a change
/// of the kept ranges; where they overlap the kept ranges, they overlap in
/// source time and the regions themselves never overlap each other.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SpeedRegion {
    pub a: f64,
    pub b: f64,
    pub speed: f64,
}

pub const SPEED_MIN: f64 = 0.25;
pub const SPEED_MAX: f64 = 4.0;

/// Sorts, clamps and drops overlapping ranges: the last one dragged wins.
pub fn normalize_speeds(list: &mut Vec<SpeedRegion>) {
    list.retain(|s| s.b - s.a > 1e-6 && s.speed.is_finite());
    for s in list.iter_mut() {
        s.speed = s.speed.clamp(SPEED_MIN, SPEED_MAX);
        s.a = s.a.max(0.0);
    }
    list.sort_by(|x, y| x.a.partial_cmp(&y.a).unwrap_or(std::cmp::Ordering::Equal));
    let mut merged: Vec<SpeedRegion> = Vec::with_capacity(list.len());
    for s in list.drain(..) {
        let overlap_end = merged.last().map_or(f64::NEG_INFINITY, |p| p.b);
        if s.a < overlap_end - 1e-9 {
            // older region keeps its span; the newcomer takes over after it
            if s.b > overlap_end {
                merged.push(SpeedRegion { a: overlap_end, b: s.b, speed: s.speed });
            }
        } else {
            merged.push(s);
        }
    }
    *list = merged;
}

/// The playback speed at source time `t`, 1.0 outside every region.
pub fn speed_at(speeds: &[SpeedRegion], t: f64) -> f64 {
    for s in speeds {
        if t >= s.a && t < s.b {
            return s.speed;
        }
    }
    1.0
}

/// Splits `[a, b]` wherever a speed region boundary falls inside it, so each
/// piece has a single constant speed.
pub fn split_by_speed(a: f64, b: f64, speeds: &[SpeedRegion]) -> Vec<(f64, f64)> {
    speed_cuts(a, b, speeds)
}

fn speed_cuts(a: f64, b: f64, speeds: &[SpeedRegion]) -> Vec<(f64, f64)> {
    let mut cuts: Vec<(f64, f64)> = vec![(a, b)];
    for s in speeds {
        let (lo, hi) = (s.a.max(a), s.b.min(b));
        if hi <= lo {
            continue;
        }
        let mut next: Vec<(f64, f64)> = Vec::with_capacity(cuts.len() + 1);
        for (x, y) in cuts {
            if hi <= x || lo >= y {
                next.push((x, y));
                continue;
            }
            if lo > x {
                next.push((x, lo));
            }
            next.push((lo, hi));
            if hi < y {
                next.push((hi, y));
            }
        }
        cuts = next;
    }
    cuts
}

/// Maps an output time back onto the source timeline.
///
/// The output is built from the kept ranges in order, each range compressed or
/// stretched by the speed regions covering it. `segments` pairs every kept
/// range with the source time its output starts at.
pub fn source_time_at(
    segments: &[(f64, f64, f64)],
    speeds: &[SpeedRegion],
    out_t: f64,
) -> f64 {
    let mut cursor = 0.0f64;
    for &(a, b, _) in segments {
        if b <= a {
            continue;
        }
        for (x, y) in speed_cuts(a, b, speeds) {
            let speed = speed_at(speeds, (x + y) * 0.5);
            let out_len = (y - x) / speed;
            if out_t < cursor + out_len || (out_t - (cursor + out_len)).abs() < 1e-9 {
                return x + (out_t - cursor).max(0.0) * speed;
            }
            cursor += out_len;
        }
    }
    segments.last().map(|&(_, b, _)| b).unwrap_or(0.0)
}

/// Output length in seconds for the kept ranges under the speed regions.
pub fn output_duration(segments: &[(f64, f64, f64)], speeds: &[SpeedRegion]) -> f64 {
    let mut total = 0.0;
    for &(a, b, _) in segments {
        if b <= a {
            continue;
        }
        for (x, y) in speed_cuts(a, b, speeds) {
            total += (y - x) / speed_at(speeds, (x + y) * 0.5);
        }
    }
    total
}

/// Which source frame shows at each output time slice, honouring both the kept
/// ranges and the speed regions. Returned as a source-frame index per output
/// sample slot, to be written at the export rate.
pub fn build_speed_map(
    frame_count: i32,
    clip_fps: i32,
    out_fps: i32,
    segments: &[(f64, f64, f64)],
    speeds: &[SpeedRegion],
) -> Vec<i32> {
    if frame_count <= 0 || clip_fps <= 0 || out_fps <= 0 {
        return Vec::new();
    }
    let dur = output_duration(segments, speeds);
    let n = (dur * out_fps as f64).round().max(1.0) as usize;
    let last_src = frame_count - 1;
    let mut map = Vec::with_capacity(n);
    let mut prev = 0i32;
    for k in 0..n {
        let out_t = k as f64 / out_fps as f64;
        let src_t = source_time_at(segments, speeds, out_t);
        let mut f = (src_t * clip_fps as f64).floor() as i32;
        f = f.clamp(0, last_src);
        // Never step backwards: the encoder would freeze on a stale frame.
        if f < prev {
            f = prev;
        }
        map.push(f);
        prev = f;
    }
    map
}

#[derive(Clone, Debug, Default)]
pub struct EditList {
    pub trims: Vec<(f64, f64)>,
    pub speeds: Vec<SpeedRegion>,
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
            "speed" => {
                let v: Vec<f64> = rest
                    .split_whitespace()
                    .filter_map(|t| t.parse().ok())
                    .collect();
                if v.len() >= 3 && v[1] > v[0] && v[2].is_finite() && v[2] > 0.0 {
                    e.speeds.push(SpeedRegion {
                        a: v[0].max(0.0),
                        b: v[1],
                        speed: v[2].clamp(SPEED_MIN, SPEED_MAX),
                    });
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
            "dz" => e.cam.dz = rest.parse().unwrap_or(e.cam.dz),
            "cs" => e.cam.cs = rest.parse().unwrap_or(e.cam.cs),
            "clk" => e.cam.clk = rest.parse().unwrap_or(e.cam.clk),
            _ => {}
        }
    }

    if e.kf.len() < 2 {
        e.kf.clear();
    }
    e.kf.sort_by(|a, b| a.t.partial_cmp(&b.t).unwrap_or(std::cmp::Ordering::Equal));
    normalize_speeds(&mut e.speeds);
    normalize_trims(&mut e.trims);
    e
}

/// Sorts, clamps and merges the kept ranges.
///
/// The frame map and the speed map normalise differently - the frame map walks
/// frames and drops anything that does not advance, the speed map walks kept
/// segments - so a hand-written `.mcl` with an unsorted or overlapping `trim`
/// rendered differently depending on whether it also carried a `speed` line.
/// Doing it once, here, is what keeps the two paths on the same timeline.
pub fn normalize_trims(trims: &mut Vec<(f64, f64)>) {
    for t in trims.iter_mut() {
        if t.0 < 0.0 {
            t.0 = 0.0;
        }
        if t.1 < t.0 {
            std::mem::swap(&mut t.0, &mut t.1);
        }
    }
    trims.retain(|t| t.1 - t.0 > 1e-6);
    trims.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
    let mut merged: Vec<(f64, f64)> = Vec::with_capacity(trims.len());
    for &(a, b) in trims.iter() {
        match merged.last_mut() {
            // overlapping or touching: one continuous range
            Some(last) if a <= last.1 + 1e-6 => last.1 = last.1.max(b),
            _ => merged.push((a, b)),
        }
    }
    *trims = merged;
}

/// Where the camera should aim: manual keyframes win inside their span.
/// Every left-button press in the track, as (time, x, y).
///
/// `btn` bit 0 is the left button, so a press is the sample where it goes from
/// clear to set. Holding the button down does not produce more than one.
pub fn click_points(track: &[TrackPt]) -> Vec<(f64, f32, f32)> {
    let mut out = Vec::new();
    let mut down = false;
    for p in track {
        let now = (p.btn & 1) != 0;
        if now && !down {
            out.push((p.t, p.x as f32, p.y as f32));
        }
        down = now;
    }
    out
}

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
/// Resamples a source-frame map onto a different output rate.
///
/// `build_frame_map` answers "which source frames were kept"; the writer stamps
/// its output at the rate it was given, so writing one frame per kept source
/// frame at another rate changes the playback speed instead of the frame rate.
/// This picks, for every output frame, the kept frame that was on screen then.
pub fn resample_map(fmap: &[i32], clip_fps: i32, out_fps: i32) -> Vec<i32> {
    if fmap.is_empty() || clip_fps <= 0 || out_fps <= 0 || clip_fps == out_fps {
        return fmap.to_vec();
    }
    let n = ((fmap.len() as f64) * (out_fps as f64) / (clip_fps as f64))
        .round()
        .max(1.0) as usize;
    (0..n)
        .map(|k| {
            let i = ((k as f64) * (clip_fps as f64) / (out_fps as f64)).floor() as usize;
            fmap[i.min(fmap.len() - 1)]
        })
        .collect()
}

/// The kept ranges in source seconds, in the order they play.
///
/// Empty trims mean the whole clip, which keeps the speed code from needing a
/// second special case.
pub fn kept_segments(clip_duration: f64, edit: &EditList) -> Vec<(f64, f64, f64)> {
    let mut out = Vec::new();
    if edit.trims.is_empty() {
        if clip_duration > 0.0 {
            out.push((0.0, clip_duration, 0.0));
        }
        return out;
    }
    // Defensive: EditList can be built in code as well as parsed, so the same
    // normalisation has to happen on the way in to every consumer.
    let mut trims = edit.trims.clone();
    normalize_trims(&mut trims);
    let mut cursor = 0.0;
    for (a, b) in trims {
        let a = a.max(0.0);
        let b = b.min(clip_duration);
        if b <= a {
            continue;
        }
        out.push((a, b, cursor));
        cursor += b - a;
    }
    out
}

pub fn build_frame_map(frame_count: i32, fps: i32, edit: &EditList) -> Vec<i32> {
    if edit.trims.is_empty() {
        return (0..frame_count).collect();
    }
    let mut trims = edit.trims.clone();
    normalize_trims(&mut trims);
    let mut map: Vec<i32> = Vec::new();
    for (a, b) in &trims {
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

#[cfg(test)]
mod resample_tests {
    use super::*;

    /// The frame count has to follow the requested rate while the *duration*
    /// stays put. Getting this wrong is what turned a 30 fps take into a
    /// double-speed export.
    #[test]
    fn rate_change_keeps_the_duration() {
        let src: Vec<i32> = (0..108).collect();
        for out in [24, 30, 50, 60, 120] {
            let got = resample_map(&src, 30, out);
            let want_s = 108.0 / 30.0;
            let got_s = got.len() as f64 / out as f64;
            assert!(
                (got_s - want_s).abs() <= 1.0 / out as f64 + 1e-9,
                "30->{out}: {got_len} frames = {got_s}s, want {want_s}s",
                got_len = got.len()
            );
        }
    }

    #[test]
    fn same_rate_is_the_identity() {
        let src = vec![0, 1, 2, 3, 4];
        assert_eq!(resample_map(&src, 30, 30), src);
        assert_eq!(resample_map(&src, 60, 60), src);
    }

    #[test]
    fn output_stays_inside_the_source_range() {
        let src: Vec<i32> = (10..40).collect();
        for out in [12, 24, 60, 240] {
            let got = resample_map(&src, 30, out);
            assert!(!got.is_empty());
            assert!(got[0] >= 10 && *got.last().unwrap() < 40);
            assert!(got.windows(2).all(|w| w[0] <= w[1]), "must not go backwards");
        }
    }

    #[test]
    fn empty_and_bad_rates_do_not_panic() {
        assert!(resample_map(&[], 30, 60).is_empty());
        assert_eq!(resample_map(&[1, 2], 0, 60), vec![1, 2]);
        assert_eq!(resample_map(&[1, 2], 30, 0), vec![1, 2]);
    }
}

#[cfg(test)]
mod speed_tests {
    use super::*;

    fn segs(v: &[(f64, f64)]) -> Vec<(f64, f64, f64)> {
        let mut c = 0.0;
        v.iter()
            .map(|&(a, b)| {
                let s = (a, b, c);
                c += b - a;
                s
            })
            .collect()
    }

    fn region(a: f64, b: f64, speed: f64) -> SpeedRegion {
        SpeedRegion { a, b, speed }
    }

    /// Nothing set: the output is exactly the kept length.
    #[test]
    fn no_regions_keeps_the_duration() {
        let s = segs(&[(0.0, 10.0)]);
        assert!((output_duration(&s, &[]) - 10.0).abs() < 1e-9);
        assert!((source_time_at(&s, &[], 4.0) - 4.0).abs() < 1e-9);
    }

    /// 2× over the middle 4 s halves that stretch.
    #[test]
    fn double_speed_shortens_the_output() {
        let s = segs(&[(0.0, 10.0)]);
        let sp = [region(3.0, 7.0, 2.0)];
        assert!((output_duration(&s, &sp) - 8.0).abs() < 1e-9);
        // 3 s of normal, then 2 s of the fast part
        assert!((source_time_at(&s, &sp, 3.5) - 4.0).abs() < 1e-9);
    }

    /// 0.5× over the middle 4 s doubles that stretch into 8 s.
    #[test]
    fn half_speed_lengthens_the_output() {
        let s = segs(&[(0.0, 10.0)]);
        let sp = [region(3.0, 7.0, 0.5)];
        assert!((output_duration(&s, &sp) - 14.0).abs() < 1e-9);
        // 3 s normal, then the slow part runs 8 s: source 5 s sits 2 s in
        assert!((source_time_at(&s, &sp, 5.0) - 4.0).abs() < 1e-9);
    }

    /// A region starting mid-way into the kept range is honoured from the clip
    /// start, not the region start.
    #[test]
    fn region_inside_a_trimmed_range() {
        let s = segs(&[(2.0, 12.0)]);
        let sp = [region(5.0, 8.0, 2.0)];
        // kept length 10 s, minus 1.5 s saved by the fast part
        assert!((output_duration(&s, &sp) - 8.5).abs() < 1e-9);
    }

    /// A region is clipped to the kept ranges: half outside costs nothing.
    #[test]
    fn region_is_clipped_to_what_is_kept() {
        let s = segs(&[(4.0, 6.0)]);
        let sp = [region(0.0, 10.0, 2.0)];
        assert!((output_duration(&s, &sp) - 1.0).abs() < 1e-9);
    }

    /// The frame map must cover the whole output and never step backwards.
    #[test]
    fn speed_map_is_monotonic_and_covers_the_output() {
        let s = segs(&[(0.0, 4.0)]);
        let sp = [region(1.0, 3.0, 4.0), region(3.0, 4.0, 0.5)];
        let m = build_speed_map(120, 30, 30, &s, &sp);
        let want = (output_duration(&s, &sp) * 30.0).round() as usize;
        assert_eq!(m.len(), want);
        assert!(m.windows(2).all(|w| w[0] <= w[1]), "must not go backwards");
        assert!(*m.last().unwrap() <= 119);
    }

    /// Overlapping regions are trimmed so the list stays sane.
    #[test]
    fn normalize_drops_the_overlap() {
        let mut v = vec![region(0.0, 5.0, 2.0), region(3.0, 8.0, 4.0)];
        normalize_speeds(&mut v);
        assert_eq!(v.len(), 2);
        assert!((v[1].a - 5.0).abs() < 1e-9);
        assert!((v[1].b - 8.0).abs() < 1e-9);
    }

    /// Parsing round-trips the line the UI writes.
    #[test]
    fn parse_reads_a_speed_line() {
        let e = parse_edit("trim 1.0 5.0\nspeed 2.0 3.5 2.00\n");
        assert_eq!(e.speeds.len(), 1);
        assert!((e.speeds[0].a - 2.0).abs() < 1e-9);
        assert!((e.speeds[0].speed - 2.0).abs() < 1e-9);
    }

    /// No trims means the whole clip is one segment for the speed code.
    #[test]
    fn empty_trims_cover_the_whole_clip() {
        let e = EditList::default();
        let s = kept_segments(12.5, &e);
        assert_eq!(s.len(), 1);
        assert!((s[0].1 - 12.5).abs() < 1e-9);
    }

    /// The shape the UI produces for a real edit: keep 3..20, triple 5..9 and
    /// quarter 12..16. Checks the numbers the preview showed the user.
    #[test]
    fn trims_and_speeds_agree_with_the_ui_estimate() {
        let mut e = EditList::default();
        e.trims = vec![(3.0, 20.0)];
        e.speeds = vec![region(5.0, 9.0, 3.0), region(12.0, 16.0, 0.25)];
        let s = kept_segments(34.05, &e);
        // 17 s kept; 4 s at 3x saves 2.667 s; 4 s at 0.25x costs 12 more
        let want = 17.0 - 4.0 + 4.0 / 3.0 + 12.0;
        assert!((output_duration(&s, &e.speeds) - want).abs() < 1e-6);

        // 3..5 plays normal (2 s of output), so the next 1 s of output covers
        // 3 s of source at 3x: output 3 s lands on source 5 + 3 = 8.
        assert!((source_time_at(&s, &e.speeds, 3.0) - 8.0).abs() < 1e-6);
        // the slow stretch runs 12..16 over 16 s of output, starting at 6.333
        assert!((source_time_at(&s, &e.speeds, 10.0) - 12.917).abs() < 0.01);
    }

    /// Every output frame in the fast stretch must skip source frames, and the
    /// slow one must repeat them. This is the whole point of the feature.
    #[test]
    fn fast_stretches_skip_and_slow_ones_repeat() {
        let mut e = EditList::default();
        e.trims = vec![(0.0, 12.0)];
        e.speeds = vec![region(3.0, 6.0, 4.0), region(6.0, 9.0, 0.25)];
        let s = kept_segments(12.0, &e);
        let m = build_speed_map(360, 30, 30, &s, &e.speeds);
        let step = |m: &[i32]| m.windows(2).map(|w| w[1] - w[0]).collect::<Vec<_>>();

        // first 3 s at 1x: one source frame per output frame
        assert!(step(&m)[..85].iter().all(|&d| d == 1));
        // 3..6 s at 4x, i.e. output 3.0 s to 3.75 s: about four source frames
        // per output frame, and the irregular steps are the rounding
        let fast: Vec<i32> = step(&m)[91..111].to_vec();
        assert!(fast.iter().all(|&d| (3..=5).contains(&d)), "fast step {fast:?}");
        // the next stretch repeats a source frame instead of skipping it
        let next: Vec<i32> = step(&m)[112..130].to_vec();
        assert!(next.iter().any(|&d| d <= 1), "expected repeats, got {next:?}");
    }

    /// Monotonic through the whole mix: an encode never seeks backwards.
    #[test]
    fn mixed_edit_never_steps_backwards() {
        let mut e = EditList::default();
        e.trims = vec![(2.0, 6.0), (10.0, 18.0)];
        e.speeds = vec![region(3.0, 5.0, 2.0), region(11.0, 15.0, 0.5), region(15.0, 17.0, 4.0)];
        let s = kept_segments(20.0, &e);
        let m = build_speed_map(600, 30, 30, &s, &e.speeds);
        assert!(!m.is_empty());
        assert!(m.windows(2).all(|w| w[0] <= w[1]));
        assert!(*m.last().unwrap() < 600);
    }
}

#[cfg(test)]
mod trim_tests {
    use super::*;

    fn segs(trims: &[(f64, f64)]) -> EditList {
        let mut e = EditList::default();
        e.trims = trims.to_vec();
        e
    }

    /// A negative start used to be clamped by one path and not the other: the
    /// frame map began at frame 0 while the speed map began five seconds before
    /// the clip and froze on the first frame.
    #[test]
    fn negative_start_is_clamped_by_both_paths() {
        let e = segs(&[(-5.0, 10.0)]);
        let s = kept_segments(20.0, &e);
        assert_eq!(s.len(), 1);
        assert!(s[0].0.abs() < 1e-9, "kept segment starts at {}", s[0].0);
        assert!((s[0].1 - 10.0).abs() < 1e-9);

        let m = build_frame_map(600, 30, &e);
        assert_eq!(m.first(), Some(&0));
        assert!((m.len() as f64 - 300.0).abs() <= 1.0, "{} frames", m.len());
    }

    /// Overlapping and out-of-order trims used to play the overlap twice in the
    /// speed path and drop it in the frame path.
    #[test]
    fn overlapping_unsorted_trims_agree_between_paths() {
        let e = segs(&[(3.0, 8.0), (1.0, 5.0)]);
        let s = kept_segments(20.0, &e);
        assert_eq!(s.len(), 1, "expected one merged range, got {s:?}");
        assert!((s[0].0 - 1.0).abs() < 1e-9 && (s[0].1 - 8.0).abs() < 1e-9);

        let m = build_frame_map(600, 30, &e);
        let s_frames: f64 = s.iter().map(|(a, b, _)| b - a).sum::<f64>() * 30.0;
        assert!(
            (m.len() as f64 - s_frames).abs() <= 2.0,
            "frame map {} vs segments {:.0}",
            m.len(),
            s_frames
        );
    }

    #[test]
    fn parse_normalises_trims_like_speeds() {
        let e = parse_edit("trim 3 8\ntrim -2 5\ntrim 2 4\n");
        assert_eq!(e.trims, vec![(0.0, 8.0)]);
    }
}
