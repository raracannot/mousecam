//! A recorded clip on disk: `master.mp4` + `track.csv` + `meta.json`.

use crate::camera::IRect;
use crate::ffmpeg::media_duration;
use crate::settings::Settings;
use crate::track::{load_track, TrackPt};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug)]
pub struct ClipInfo {
    pub dir: PathBuf,
    pub master: PathBuf,
    pub mon: IRect,
    pub fps: i32,
    pub frame_count: i32,
    pub duration: f64,
    pub track: Vec<TrackPt>,
    /// camera tick index used for each output frame (empty for older clips)
    pub frame_ticks: Vec<u32>,
}

fn json_num(s: &str, key: &str) -> Option<f64> {
    let pat = format!("\"{}\"", key);
    let p = s.find(&pat)?;
    let rest = &s[p + pat.len()..];
    let c = rest.find(':')?;
    let v = rest[c + 1..].trim_start();
    let end = v
        .find(|ch: char| {
            !(ch.is_ascii_digit() || ch == '-' || ch == '+' || ch == '.' || ch == 'e' || ch == 'E')
        })
        .unwrap_or(v.len());
    v[..end].parse().ok()
}

fn json_i32(s: &str, key: &str, def: i32) -> i32 {
    json_num(s, key).map(|v| v as i32).unwrap_or(def)
}

fn parse_monitor(meta: &str) -> Option<IRect> {
    let p = meta.find("\"monitor\"")?;
    let b = meta[p..].find('{')? + p;
    let e = meta[b..].find('}')? + b;
    let block = &meta[b..e];
    Some(IRect::new(
        json_num(block, "x")? as i32,
        json_num(block, "y")? as i32,
        json_num(block, "w")? as i32,
        json_num(block, "h")? as i32,
    ))
}

fn aspect_from_ratio(w: i32, h: i32) -> i32 {
    if h <= 0 {
        return 0;
    }
    let a = w as f32 / h as f32;
    let mut best = 0;
    let mut bd = f32::MAX;
    for (i, (_, v)) in crate::settings::ASPECTS.iter().enumerate() {
        let d = (a - v).abs();
        if d < bd {
            bd = d;
            best = i as i32;
        }
    }
    best
}

/// Locates ffmpeg: env override, next to the binary, or in a sibling `dist/`.
pub fn find_ffmpeg() -> Option<PathBuf> {
    // Resolved once: this is called from every still/bake/export.
    static CACHED: std::sync::OnceLock<Option<PathBuf>> = std::sync::OnceLock::new();
    CACHED.get_or_init(find_ffmpeg_uncached).clone()
}

fn find_ffmpeg_uncached() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("MC_FFMPEG") {
        let pb = PathBuf::from(p);
        if pb.is_file() {
            return Some(pb);
        }
    }
    let exe = std::env::current_exe().ok()?;
    let mut dir = exe.parent()?.to_path_buf();
    for _ in 0..6 {
        for cand in ["ffmpeg.exe", "dist/ffmpeg.exe", "bin/ffmpeg.exe", "tools/ffmpeg.exe"] {
            let p = dir.join(cand);
            if p.is_file() {
                return Some(p);
            }
        }
        if !dir.pop() {
            break;
        }
    }
    // PATH
    if let Ok(paths) = std::env::var("PATH") {
        for d in std::env::split_paths(&paths) {
            let p = d.join("ffmpeg.exe");
            if p.is_file() {
                return Some(p);
            }
        }
    }
    None
}

pub fn load_clip(dir: &Path) -> Result<ClipInfo, String> {
    let meta_path = dir.join("meta.json");
    let meta = std::fs::read_to_string(&meta_path)
        .map_err(|e| format!("读取 {} 失败: {e}", meta_path.display()))?;

    let mon = parse_monitor(&meta).ok_or_else(|| "meta.json 里没有有效的显示器矩形".to_string())?;
    if mon.w <= 0 || mon.h <= 0 {
        return Err("meta.json 里的显示器矩形无效".into());
    }

    let mut fps = json_i32(&meta, "fps", 30);
    if fps < 5 {
        fps = 30;
    }

    let track_path = dir.join("track.csv");
    let track = load_track(&track_path)
        .map_err(|e| format!("读取 {} 失败: {e}", track_path.display()))?;
    if track.is_empty() {
        return Err("track.csv 为空".into());
    }

    let master = dir.join("master.mp4");

    // Prefer what the recorder wrote. Probing costs a whole ffmpeg process
    // launch and used to happen on every still/bake.
    let recorded_dur = json_f64(&meta, "duration", 0.0);
    let recorded_frames = json_i32(&meta, "frames", 0);

    let duration = if recorded_dur > 0.0 {
        recorded_dur
    } else {
        let probed = match find_ffmpeg() {
            Some(ff) => memo_duration(&ff, &master),
            None => 0.0,
        };
        if probed > 0.0 {
            probed
        } else {
            track.last().map(|p| p.t).unwrap_or(0.0)
        }
    };

    let frame_count = if recorded_frames > 0 {
        recorded_frames
    } else {
        ((duration * fps as f64).round() as i32).max(1)
    };

    let mut frame_ticks: Vec<u32> = Vec::new();
    if let Ok(txt) = std::fs::read_to_string(dir.join("frames.csv")) {
        for line in txt.lines() {
            let l = line.trim();
            if l.is_empty() || l.starts_with('#') {
                continue;
            }
            if let Some((_, v)) = l.split_once(',') {
                if let Ok(v) = v.trim().parse::<u32>() {
                    frame_ticks.push(v);
                }
            }
        }
    }

    Ok(ClipInfo {
        dir: dir.to_path_buf(),
        master,
        mon,
        fps,
        frame_count,
        duration,
        track,
        frame_ticks,
    })
}

/// Settings as recorded, with the edit list applied on top.
pub fn settings_from_meta(dir: &Path) -> Result<Settings, String> {
    let meta = std::fs::read_to_string(dir.join("meta.json"))
        .map_err(|e| format!("读取 meta.json 失败: {e}"))?;
    let mut s = Settings::default();
    s.fps = json_i32(&meta, "fps", 30).max(5);
    s.out_width = json_i32(&meta, "outWidth", 1280).max(16);
    s.aspect_idx = json_i32(
        &meta,
        "aspectIdx",
        aspect_from_ratio(
            json_i32(&meta, "outWidth", 1280),
            json_i32(&meta, "outHeight", 720),
        ),
    ) as usize;
    if s.aspect_idx >= crate::settings::ASPECTS.len() {
        s.aspect_idx = 0;
    }
    s.zoom = json_num(&meta, "zoom").unwrap_or(1.0) as f32;
    s.speed_expand = json_num(&meta, "speedExpand").unwrap_or(1.5) as f32;
    s.speed_threshold = json_num(&meta, "speedThreshold").unwrap_or(1500.0) as f32;
    s.smooth = json_num(&meta, "smooth").unwrap_or(55.0) as f32;
    s.speed_resp = json_num(&meta, "speedResp").unwrap_or(35.0) as f32;
    s.follow_hz = json_num(&meta, "followHz").unwrap_or(2.2) as f32;
    s.lookahead_ms = json_num(&meta, "lookaheadMs").unwrap_or(60.0) as f32;
    Ok(s)
}

/// `media_duration` spawns ffmpeg, so remember the answer per file. Keyed on
/// path + size + mtime so a re-recorded clip is re-probed.
fn memo_duration(ffmpeg: &Path, file: &Path) -> f64 {
    use std::collections::HashMap;
    use std::sync::Mutex;
    use std::sync::OnceLock;

    static CACHE: OnceLock<Mutex<HashMap<String, f64>>> = OnceLock::new();
    let cache = CACHE.get_or_init(|| Mutex::new(HashMap::new()));

    let md = std::fs::metadata(file).ok();
    let key = format!(
        "{}|{}|{:?}",
        file.display(),
        md.as_ref().map(|m| m.len()).unwrap_or(0),
        md.as_ref().and_then(|m| m.modified().ok())
    );

    if let Ok(g) = cache.lock() {
        if let Some(v) = g.get(&key) {
            return *v;
        }
    }
    let d = crate::ffmpeg::media_duration(ffmpeg, file);
    if d > 0.0 {
        if let Ok(mut g) = cache.lock() {
            g.insert(key, d);
        }
    }
    d
}

/// Reads a float field out of meta.json without pulling in serde.
pub fn json_f64(text: &str, key: &str, dflt: f64) -> f64 {
    let pat = format!("\"{key}\"");
    let Some(i) = text.find(&pat) else { return dflt };
    let rest = &text[i + pat.len()..];
    let Some(colon) = rest.find(':') else { return dflt };
    let tail = rest[colon + 1..].trim_start();
    let end = tail
        .find(|c: char| c != '-' && c != '+' && c != '.' && !c.is_ascii_digit() && c != 'e' && c != 'E')
        .unwrap_or(tail.len());
    tail[..end].trim().parse::<f64>().unwrap_or(dflt)
}
