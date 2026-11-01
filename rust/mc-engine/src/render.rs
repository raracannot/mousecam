//! Offline re-render: bake the camera path from the trace, then decode the
//! master, crop + composite the cursor, and encode.

use crate::camera::{Camera, IRect, Vec2};
use crate::clip::ClipInfo;
use crate::cursor::{arrow_sprite, draw, Sprite};
use crate::edit::{build_frame_map, cursor_at, EditList};
use crate::ffmpeg::{media_duration as _dur, FrameReader, FrameWriter, VideoFormat};
use crate::resample::Resampler;
use crate::settings::Settings;
use std::path::{Path, PathBuf};
use std::time::Instant;

pub struct RenderSummary {
    pub frames: i32,
    pub duration: f64,
    pub elapsed: f64,
    pub out_path: PathBuf,
}

#[derive(Clone, Copy, Debug)]
pub struct CamFrameOut {
    pub cx: f32,
    pub cy: f32,
    pub w: f32,
    pub h: f32,
}

/// Bake one viewport per source frame. Pure CPU, no video is decoded.
pub fn bake_path(clip: &ClipInfo, s: &Settings, edit: &EditList) -> (Vec<CamFrameOut>, f64) {
    let t0 = Instant::now();
    let mut cam = Camera::new();
    cam.set_screen(clip.mon);
    cam.reset(cursor_at(&clip.track, edit, 0.0));
    cam.tick(s, cursor_at(&clip.track, edit, 0.0), 1.0 / 250.0);

    let mut out = Vec::with_capacity(clip.frame_count as usize);

    // Replay the camera on the SAME tick grid the live recorder used: track.csv
    // is a 250 Hz log of every camera tick, so driving the bake from its
    // timestamps reproduces the recorded framing instead of approximating it.
    let mut k = 0usize;
    let mut t_prev = 0.0f64;
    let mut applied: u64 = 1; // the seed tick above

    for i in 0..clip.frame_count {
        let tt = i as f64 / clip.fps as f64;

        // Preferred path: replay exactly the ticks the recorder used for this
        // frame. The speed envelope is sensitive to tick phase, so matching the
        // count is what makes the export frame-identical to the live capture.
        if let Some(&want) = clip.frame_ticks.get(i as usize) {
            let want = want as u64;
            while applied < want && k < clip.track.len() {
                let tk = clip.track[k].t;
                let mut dt = tk - t_prev;
                if dt < 1.0 / 1000.0 {
                    dt = 1.0 / 1000.0;
                }
                if dt > 1.0 / 25.0 {
                    dt = 1.0 / 25.0;
                }
                let pos = cursor_at(&clip.track, edit, tk);
                cam.tick(s, pos, dt);
                t_prev = tk;
                k += 1;
                applied += 1;
            }
            let snap = cam.snapshot();
            out.push(CamFrameOut {
                cx: snap.center.x,
                cy: snap.center.y,
                w: snap.src_w,
                h: snap.src_h,
            });
            continue;
        }

        while k < clip.track.len() && clip.track[k].t <= tt {
            let tk = clip.track[k].t;
            let mut dt = tk - t_prev;
            if dt < 1.0 / 1000.0 {
                dt = 1.0 / 1000.0;
            }
            if dt > 1.0 / 25.0 {
                dt = 1.0 / 25.0;
            }
            let pos = cursor_at(&clip.track, edit, tk);
            cam.tick(s, pos, dt);
            t_prev = tk;
            k += 1;
        }
        let snap = cam.snapshot();
        out.push(CamFrameOut {
            cx: snap.center.x,
            cy: snap.center.y,
            w: snap.src_w,
            h: snap.src_h,
        });
    }
    (out, t0.elapsed().as_secs_f64() * 1000.0)
}

pub fn frame_src_rect(cf: &CamFrameOut, mon: IRect) -> IRect {
    let mut w = cf.w.min(mon.w as f32);
    let mut h = cf.h.min(mon.h as f32);
    let mut x = cf.cx - w * 0.5;
    let mut y = cf.cy - h * 0.5;
    if x < mon.x as f32 {
        x = mon.x as f32;
    }
    if y < mon.y as f32 {
        y = mon.y as f32;
    }
    if x + w > mon.right() as f32 {
        x = mon.right() as f32 - w;
    }
    if y + h > mon.bottom() as f32 {
        y = mon.bottom() as f32 - h;
    }
    if w < 2.0 {
        w = 2.0;
    }
    if h < 2.0 {
        h = 2.0;
    }
    IRect::new(x.round() as i32, y.round() as i32, w.round() as i32, h.round() as i32)
}

pub fn render_clip(
    clip: &ClipInfo,
    ffmpeg: &Path,
    out: &Path,
    s: &Settings,
    edit: &EditList,
    fmt: VideoFormat,
    crf: i32,
    mut progress: impl FnMut(i32, i32),
) -> Result<RenderSummary, String> {
    let out_w = s.out_width & !1;
    let out_h = s.out_height();
    if out_w < 16 || out_h < 16 {
        return Err("输出尺寸过小".into());
    }

    let (path, bake_ms) = bake_path(clip, s, edit);
    if let Ok(dump) = std::env::var("MC_DUMP_RECTS") {
        let mut txt = String::from("# frame,cx,cy,w,h\n");
        for (i, f) in path.iter().enumerate() {
            txt.push_str(&format!("{},{:.3},{:.3},{:.3},{:.3}\n", i, f.cx, f.cy, f.w, f.h));
        }
        let _ = std::fs::write(dump, txt);
    }
    let fmap = build_frame_map(clip.frame_count, clip.fps, edit);
    if fmap.is_empty() {
        return Err("编辑清单没有产生任何帧".into());
    }

    log_line(&format!(
        "clip {}x{} @{} fps  {:.2}s  {} frames   bake {:.0} ms",
        clip.mon.w, clip.mon.h, clip.fps, clip.duration, clip.frame_count, bake_ms
    ));
    log_line(&format!(
        "edit trims={} kf={}  ->  {} out frames ({:.2}s)",
        edit.trims.len(),
        edit.kf.len(),
        fmap.len(),
        fmap.len() as f64 / s.fps as f64
    ));
    log_line(&format!(
        "out  {}x{}  zoom={:.2} expand={:.2} smooth={:.0} follow={:.2}",
        out_w, out_h, s.zoom, s.speed_expand, s.smooth, s.follow_hz
    ));

    let mut reader = FrameReader::open(ffmpeg, &clip.master, None, clip.mon.w, clip.mon.h)
        .map_err(|e| format!("打开母片失败: {e}"))?;
    let mut writer = FrameWriter::open(ffmpeg, out, out_w, out_h, s.fps, fmt, crf)?;

    let sprite: Option<Sprite> = arrow_sprite();

    let mut frame_buf = vec![0u32; (clip.mon.w * clip.mon.h) as usize];
    let mut crop_buf = vec![0u32; (out_w * out_h) as usize];
    let mut rs = Resampler::new();

    let t0 = Instant::now();
    let mut written = 0i32;
    let mut src_cur = 0i32;
    let total = fmap.len() as i32;

    for k in 0..total {
        let target = fmap[k as usize];
        while src_cur <= target {
            if !reader.read_frame(&mut frame_buf) {
                src_cur = -1;
                break;
            }
            src_cur += 1;
        }
        if src_cur < 0 {
            log_line(&format!("decode ended at out frame {k}"));
            break;
        }

        let r = frame_src_rect(&path[target as usize], clip.mon);
        let mut lx = r.x - clip.mon.x;
        let mut ly = r.y - clip.mon.y;
        let mut rw = r.w;
        let mut rh = r.h;
        if lx < 0 {
            lx = 0;
        }
        if ly < 0 {
            ly = 0;
        }
        if lx + rw > clip.mon.w {
            rw = clip.mon.w - lx;
        }
        if ly + rh > clip.mon.h {
            rh = clip.mon.h - ly;
        }
        if rw < 4 || rh < 4 {
            continue;
        }

        rs.prep(lx as f32, ly as f32, rw as f32, rh as f32, out_w, out_h);
        rs.run(&frame_buf, clip.mon.w, clip.mon.h, &mut crop_buf, out_w);

        if let Some(spr) = &sprite {
            let mpt: Vec2 = cursor_at(&clip.track, edit, target as f64 / s.fps as f64);
            let sc = out_w as f32 / rw as f32;
            // same rule as the live recorder, taken from the baked rect so an
            // export matches what was on screen while recording
            let grow = crate::camera::growth_factor(rw as f32, out_w, s.zoom);
            draw(
                &mut crop_buf,
                out_w,
                out_h,
                (mpt.x - r.x as f32) * sc,
                (mpt.y - r.y as f32) * sc,
                sc * grow,
                spr,
            );
        }

        if writer.write_frame(&crop_buf).is_err() {
            break;
        }
        written += 1;
        if written % 30 == 0 || written == total {
            progress(written, total);
        }
    }

    let code = writer.finish();
    let elapsed = t0.elapsed().as_secs_f64();
    if code != 0 {
        log_line(&format!("ffmpeg exited with code {code}"));
    }

    Ok(RenderSummary {
        frames: written,
        duration: written as f64 / s.fps as f64,
        elapsed,
        out_path: out.to_path_buf(),
    })
}

fn log_line(msg: &str) {
    println!("{msg}");
    if let Some(dir) = std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_path_buf())) {
        use std::io::Write;
        if let Ok(mut f) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(dir.join("mc-render.log"))
        {
            let _ = writeln!(f, "{msg}");
        }
    }
}

/// Exposed for the CLI: duration probe of the master.
pub fn clip_duration(ffmpeg: &Path, clip: &ClipInfo) -> f64 {
    _dur(ffmpeg, &clip.master)
}
