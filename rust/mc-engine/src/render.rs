//! Offline re-render: bake the camera path from the trace, then decode the
//! master, crop + composite the cursor, and encode.

use crate::camera::{Camera, IRect, Vec2};
use crate::clip::ClipInfo;
use crate::cursor::{arrow_sprite, draw, Sprite};
use crate::edit::{
    build_frame_map, build_speed_map, cursor_at, kept_segments, output_duration, resample_map,
    EditList,
};
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
    // A take recorded while the encoders were still warming up has frames whose
    // tick never advanced. Replaying those freezes the camera, which is what made
    // the opening look like it ignored the cursor. When the grid is not strictly
    // increasing anywhere, replay by time instead.
    let ticks_ok = clip.frame_ticks.windows(2).all(|w| w[1] > w[0]);

    let mut k = 0usize;
    let mut t_prev = 0.0f64;
    let mut applied: u64 = 1; // the seed tick above

    for i in 0..clip.frame_count {
        let tt = i as f64 / clip.fps as f64;

        // Preferred path: replay exactly the ticks the recorder used for this
        // frame. The speed envelope is sensitive to tick phase, so matching the
        // count is what makes the export frame-identical to the live capture.
        if let Some(&want) = clip.frame_ticks.get(i as usize).filter(|_| ticks_ok) {
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

/// The crop window in source pixels, *not* rounded.
///
/// The camera solves in continuous coordinates and the resampler interpolates
/// from fractional origins, so rounding here throws away motion the rest of the
/// chain can represent: a slow pan would sit still for several frames and then
/// jump a whole pixel. `frame_src_rect` is the rounded form, for callers that
/// really do need integer pixels.
pub fn frame_src_rectf(cf: &CamFrameOut, mon: IRect) -> (f32, f32, f32, f32) {
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
    (x, y, w, h)
}

pub fn frame_src_rect(cf: &CamFrameOut, mon: IRect) -> IRect {
    let (x, y, w, h) = frame_src_rectf(cf, mon);
    IRect::new(x.round() as i32, y.round() as i32, w.round() as i32, h.round() as i32)
}

/// Escape hatch for A/B comparisons: MC_SUBPIXEL=0 restores the old behaviour.
fn subpixel() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| match std::env::var("MC_SUBPIXEL") {
        Ok(v) => v != "0" && !v.eq_ignore_ascii_case("false"),
        Err(_) => true,
    })
}

pub fn render_clip(
    clip: &ClipInfo,
    ffmpeg: &Path,
    out: &Path,
    s: &Settings,
    edit: &EditList,
    fmt: VideoFormat,
    crf: i32,
    mut progress: impl FnMut(i32, i32) -> bool,
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
    // Speed regions work in source time, so they need the kept ranges rather
    // than the frame list: a range can be sped up or slowed down independently
    // of how many source frames it holds.
    let segs = kept_segments(clip.duration, edit);
    if segs.is_empty() {
        return Err("编辑清单没有产生任何帧".into());
    }
    let out_total = if edit.speeds.is_empty() {
        None
    } else {
        let d = output_duration(&segs, &edit.speeds);
        if d <= 0.0 {
            return Err("编辑清单没有产生任何帧".into());
        }
        Some(d)
    };

    log_line(&format!(
        "clip {}x{} @{} fps  {:.2}s  {} frames   bake {:.0} ms",
        clip.mon.w, clip.mon.h, clip.fps, clip.duration, clip.frame_count, bake_ms
    ));
    // `fmap` holds *source* frame indices. When the export asks for a different
    // rate, resample it: each output frame picks the source frame that was on
    // screen at that moment. Writing one output frame per source frame at a
    // different `-r` would change nothing but the playback speed.
    //
    // Speed regions take over that mapping when present: the output length then
    // depends on how fast each stretch plays, not just on which frames survived
    // the trims.
    let src_of_out: Vec<i32> = if out_total.is_some() {
        build_speed_map(clip.frame_count, clip.fps, s.fps, &segs, &edit.speeds)
    } else {
        resample_map(&build_frame_map(clip.frame_count, clip.fps, edit), clip.fps, s.fps)
    };
    if src_of_out.is_empty() {
        return Err("编辑清单没有产生任何帧".into());
    }

    log_line(&format!(
        "edit trims={} speeds={} kf={}  ->  {} out frames ({:.2}s)",
        edit.trims.len(),
        edit.speeds.len(),
        edit.kf.len(),
        src_of_out.len(),
        src_of_out.len() as f64 / s.fps as f64
    ));
    log_line(&format!(
        "out  {}x{}  zoom={:.2} expand={:.2} smooth={:.0} follow={:.2}",
        out_w, out_h, s.zoom, s.speed_expand, s.smooth, s.follow_hz
    ));

    let mut reader = FrameReader::open(ffmpeg, &clip.master, None, clip.mon.w, clip.mon.h)
        .map_err(|e| format!("打开母片失败: {e}"))?;
    let mut writer = FrameWriter::open(ffmpeg, out, out_w, out_h, s.fps, fmt, crf)?;

    let sprite: Option<Sprite> = arrow_sprite();
    // The pointer drawn into the take is a look, not the record: smoothing it
    // here leaves track.csv and master.mp4 untouched, and lets an old clip be
    // re-rendered with a steadier cursor without recording it again.
    let draw_track = crate::track::smooth_track(&clip.track, s.cursor_smooth_ms);
    let clicks = if s.click_ring {
        crate::edit::click_points(&clip.track)
    } else {
        Vec::new()
    };
    // how long a ring lives, in seconds
    const CLICK_SECS: f64 = 0.45;

    let mut frame_buf = vec![0u32; (clip.mon.w * clip.mon.h) as usize];
    let mut crop_buf = vec![0u32; (out_w * out_h) as usize];
    let mut rs = Resampler::new();

    let t0 = Instant::now();
    let mut written = 0i32;
    let mut src_cur = 0i32;
    let total = src_of_out.len() as i32;

    for k in 0..total {
        let target = src_of_out[k as usize];
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

        let (mut lx, mut ly, mut rw, mut rh) = if subpixel() {
            let (fx, fy, fw, fh) = frame_src_rectf(&path[target as usize], clip.mon);
            (fx - clip.mon.x as f32, fy - clip.mon.y as f32, fw, fh)
        } else {
            let r = frame_src_rect(&path[target as usize], clip.mon);
            (
                (r.x - clip.mon.x) as f32,
                (r.y - clip.mon.y) as f32,
                r.w as f32,
                r.h as f32,
            )
        };
        if lx < 0.0 {
            lx = 0.0;
        }
        if ly < 0.0 {
            ly = 0.0;
        }
        if lx + rw > clip.mon.w as f32 {
            rw = clip.mon.w as f32 - lx;
        }
        if ly + rh > clip.mon.h as f32 {
            rh = clip.mon.h as f32 - ly;
        }
        if rw < 4.0 || rh < 4.0 {
            continue;
        }
        // The cursor and the click rings are placed in screen coordinates, so
        // they need the same unrounded origin the picture is sampled from.
        let (ox, oy) = (lx + clip.mon.x as f32, ly + clip.mon.y as f32);

        // Fractional origin: prep turns the remainder into bilinear weights.
        rs.prep(lx, ly, rw, rh, out_w, out_h);
        rs.run(&frame_buf, clip.mon.w, clip.mon.h, &mut crop_buf, out_w);

        let now_t = target as f64 / clip.fps as f64;
        let sc_all = out_w as f32 / rw as f32;

        // Rings go under the pointer so the arrow stays readable on top.
        for &(ct, cx, cy) in &clicks {
            let age = (now_t - ct) / CLICK_SECS;
            if !(0.0..=1.0).contains(&age) {
                continue;
            }
            crate::cursor::draw_click_ring(
                &mut crop_buf,
                out_w,
                out_h,
                (cx - ox) * sc_all,
                (cy - oy) * sc_all,
                age as f32,
                sc_all,
            );
        }

        // 0.2+ paints the pointer into the master, so cropping it already
        // carries one arrow; compositing another would show two.
        if should_composite_pointer(clip) {
            if let Some(spr) = &sprite {
                let mpt: Vec2 = cursor_at(&draw_track, edit, target as f64 / clip.fps as f64);
                let sc = out_w as f32 / rw as f32;
                // same rule as the live recorder, taken from the baked rect so an
                // export matches what was on screen while recording
                let grow = crate::camera::growth_factor(rw as f32, out_w, s.zoom);
                draw(
                    &mut crop_buf,
                    out_w,
                    out_h,
                    (mpt.x - ox) * sc,
                    (mpt.y - oy) * sc,
                    sc * grow,
                    spr,
                );
            }
        }

        if writer.write_frame(&crop_buf).is_err() {
            break;
        }
        written += 1;
        if (written % 30 == 0 || written == total) && !progress(written, total) {
            // The caller wants to stop: kill the encoder before touching the
            // file, then remove it so nothing half-written looks finished.
            writer.abort();
            let _ = std::fs::remove_file(out);
            return Err("导出已取消".into());
        }
    }

    let (code, why) = writer.finish();
    let elapsed = t0.elapsed().as_secs_f64();
    if code != 0 {
        log_line(&format!("ffmpeg exited with code {code}: {why}"));
        // The file exists but is not a video; keeping it would look like success.
        let _ = std::fs::remove_file(out);
        return Err(if why.is_empty() {
            format!("编码器异常退出 ({code})")
        } else {
            format!("编码器异常退出 ({code}): {why}")
        });
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

/// Whether the export has to paint a pointer of its own.
///
/// The recorder copy is the authority: a take that already has the pointer in
/// the master must not get a second one, or the export shows two arrows.
fn should_composite_pointer(clip: &ClipInfo) -> bool {
    !clip.pointer_in_master
}

#[cfg(test)]
mod pointer_tests {
    use super::should_composite_pointer;
    use crate::clip::ClipInfo;
    use std::path::PathBuf;

    fn clip(pointer_in_master: bool) -> ClipInfo {
        ClipInfo {
            dir: PathBuf::new(),
            master: PathBuf::new(),
            pointer_in_master,
            mon: crate::camera::IRect::new(0, 0, 1920, 1080),
            fps: 30,
            frame_count: 1,
            duration: 1.0,
            track: Vec::new(),
            frame_ticks: Vec::new(),
        }
    }

    /// A 0.2+ take already has the arrow in the master; drawing another put two
    /// cursors in the exported clip.
    #[test]
    fn take_with_pointer_in_master_is_not_painted_again() {
        assert!(!should_composite_pointer(&clip(true)));
    }

    /// Older takes have no pointer in the master, so the export supplies one.
    #[test]
    fn take_without_pointer_gets_one_composited() {
        assert!(should_composite_pointer(&clip(false)));
    }
}
