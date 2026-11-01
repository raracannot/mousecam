//! Live recorder: grab -> camera tick -> master + follow-cam encode, with a
//! trace written alongside so the clip can be re-framed later.

use crate::camera::{Camera, IRect, Vec2};
use crate::capture::Capture;
use crate::cursor::{draw, SpriteCache};
use crate::ffmpeg::{FrameWriter, VideoFormat};
use crate::resample::Resampler;
use crate::settings::Settings;
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

/// One downscaled follow-cam frame, shared with whoever shows a live preview.
#[derive(Clone)]
pub struct PreviewShot {
    pub w: u32,
    pub h: u32,
    pub px: Vec<u32>,
}

pub type PreviewSink = Arc<std::sync::Mutex<Option<PreviewShot>>>;

pub fn new_sink() -> PreviewSink {
    Arc::new(std::sync::Mutex::new(None))
}

pub struct RecorderConfig {
    pub mon: IRect,
    pub out_root: PathBuf,
    pub settings: Settings,
    pub record_master: bool,
    pub format: VideoFormat,
    pub quality: i32,
    pub camera_format: VideoFormat,
    pub camera_quality: i32,
    /// optional live preview output (the recorder is the only owner of the
    /// DXGI duplication, so it has to publish frames itself)
    pub preview: Option<PreviewSink>,
}

impl Default for RecorderConfig {
    fn default() -> Self {
        Self {
            mon: IRect::new(0, 0, 1920, 1080),
            out_root: PathBuf::from("captures"),
            settings: Settings::default(),
            record_master: true,
            format: VideoFormat::Mp4H264,
            quality: 20,
            camera_format: VideoFormat::Mp4H264,
            camera_quality: 22,
            preview: None,
        }
    }
}

pub struct RecSummary {
    pub frames: i32,
    pub duration: f64,
    pub out_dir: PathBuf,
    pub dropped: u32,
}

pub struct Recorder {
    stop: Arc<AtomicBool>,
    handle: Option<std::thread::JoinHandle<Result<RecSummary, String>>>,
    pub out_dir: PathBuf,
}

fn now_stamp() -> String {
    unsafe {
        let st = windows::Win32::System::SystemInformation::GetLocalTime();
        format!(
            "{:04}{:02}{:02}_{:02}{:02}{:02}",
            st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond
        )
    }
}

fn meta_json(cfg: &RecorderConfig, duration: f64, frames: i64) -> String {
    let s = &cfg.settings;
    format!(
        concat!(
            "{{\n",
            "  \"app\": \"MouseCam\",\n",
            "  \"monitor\": {{\"x\": {}, \"y\": {}, \"w\": {}, \"h\": {}}},\n",
            "  \"fps\": {},\n",
            "  \"outWidth\": {},\n",
            "  \"outHeight\": {},\n",
            "  \"aspectIdx\": {},\n",
            "  \"zoom\": {:.4},\n",
            "  \"speedExpand\": {:.4},\n",
            "  \"speedThreshold\": {:.1},\n",
            "  \"smooth\": {:.1},\n",
            "  \"speedResp\": {:.1},\n",
            "  \"followHz\": {:.3},\n",
            "  \"lookaheadMs\": {:.1},\n",
            // duration/frames are recorded here so loaders never have to probe
            // the file with ffmpeg to find out how long the clip is
            "  \"duration\": {:.6},\n",
            "  \"frames\": {}\n",
            "}}\n"
        ),
        cfg.mon.x,
        cfg.mon.y,
        cfg.mon.w,
        cfg.mon.h,
        s.fps,
        s.out_width,
        s.out_height(),
        s.aspect_idx,
        s.zoom,
        s.speed_expand,
        s.speed_threshold,
        s.smooth,
        s.speed_resp,
        s.follow_hz,
        s.lookahead_ms,
        duration,
        frames
    )
}

fn cursor_pos() -> Vec2 {
    unsafe {
        let mut p = windows::Win32::Foundation::POINT::default();
        if windows::Win32::UI::WindowsAndMessaging::GetCursorPos(&mut p).is_ok() {
            Vec2::new(p.x as f32, p.y as f32)
        } else {
            Vec2::default()
        }
    }
}

fn buttons() -> u32 {
    unsafe {
        use windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;
        let l = GetAsyncKeyState(0x01) as u16;
        let r = GetAsyncKeyState(0x02) as u16;
        let m = GetAsyncKeyState(0x04) as u16;
        let mut b = 0;
        if l & 0x8000 != 0 {
            b |= 1;
        }
        if r & 0x8000 != 0 {
            b |= 2;
        }
        if m & 0x8000 != 0 {
            b |= 4;
        }
        b
    }
}

impl Recorder {
    pub fn start(cfg: RecorderConfig, ffmpeg: PathBuf) -> Result<Self, String> {
        let cap = Capture::open(cfg.mon)?;

        let out_dir = cfg.out_root.join(format!("rec_{}", now_stamp()));
        std::fs::create_dir_all(&out_dir)
            .map_err(|e| format!("创建录制目录失败 {}: {e}（“拒绝访问”多是安全软件拦截，可在设置里换一个输出文件夹）", out_dir.display()))?;

        let stop = Arc::new(AtomicBool::new(false));
        let stop2 = stop.clone();
        let dir2 = out_dir.clone();

        let handle = std::thread::Builder::new()
            .name("mc-recorder".into())
            .spawn(move || {
                let mut cap = cap;
                run(cfg, ffmpeg, &mut cap, &dir2, stop2)
            })
            .map_err(|e| format!("启动录制线程失败: {e}"))?;

        Ok(Self {
            stop,
            handle: Some(handle),
            out_dir,
        })
    }

    pub fn request_stop(&self) {
        self.stop.store(true, Ordering::Relaxed);
    }

    pub fn stop(mut self) -> Result<RecSummary, String> {
        self.stop.store(true, Ordering::Relaxed);
        match self.handle.take() {
            Some(h) => h.join().map_err(|_| "录制线程崩溃".to_string())?,
            None => Err("录制线程已结束".into()),
        }
    }
}

impl Drop for Recorder {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
    }
}

/// State the capture loop reads from the camera thread.
struct CamShared {
    pos: Vec2,
    snap: crate::camera::CamSnapshot,
    btn: u32,
    ticks: u64,
}

fn run(
    cfg: RecorderConfig,
    ffmpeg: PathBuf,
    cap: &mut Capture,
    out_dir: &Path,
    stop: Arc<AtomicBool>,
) -> Result<RecSummary, String> {
    let s = cfg.settings.clone();
    let fps = s.fps.max(5);
    let out_w = (s.out_width & !1).max(16);
    let out_h = s.out_height().max(16);
    let mon = cfg.mon;

    let mut master = if cfg.record_master {
        Some(
            FrameWriter::open(
                &ffmpeg,
                &out_dir.join("master.mp4"),
                mon.w,
                mon.h,
                fps,
                cfg.format,
                cfg.quality,
            )
            .map_err(|e| format!("master 编码器启动失败: {e}"))?,
        )
    } else {
        None
    };

    let mut camera = FrameWriter::open(
        &ffmpeg,
        &out_dir.join("camera.mp4"),
        out_w,
        out_h,
        fps,
        cfg.camera_format,
        cfg.camera_quality,
    )
    .map_err(|e| format!("camera 编码器启动失败: {e}"))?;

    let track_file = OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(out_dir.join("track.csv"))
        .map_err(|e| format!("创建 track.csv 失败: {e}"))?;
    let mut track = BufWriter::new(track_file);
    let _ = writeln!(track, "# MouseCam track v1 fps={fps}");

    // ---- camera runs on its own 250 Hz clock, exactly like the offline bake.
    // Tying it to the capture rate made the speed estimate (and therefore the
    // expand-fast viewport) depend on the frame rate.
    const CAM_HZ: f64 = 250.0;

    // One clock for the camera thread, the trace and the encoded timeline, so
    // `track.csv` t=0 is frame 0 of the video and the offline bake lines up.
    let t0_shared = Instant::now();
    let shared = Arc::new(std::sync::Mutex::new(CamShared {
        pos: cursor_pos(),
        snap: Default::default(),
        btn: 0,
        ticks: 1, // the seed tick
    }));

    {
        let shared = shared.clone();
        let s2 = s.clone();
        let stop2 = stop.clone();
        let t0_cam = t0_shared;
        let mut cam = Camera::new();
        cam.set_screen(mon);
        let start_pos = cursor_pos();
        cam.reset(start_pos);
        cam.tick(&s2, start_pos, 1.0 / CAM_HZ);
        {
            let mut g = shared.lock().unwrap();
            g.pos = start_pos;
            g.snap = cam.snapshot();
        }

        std::thread::Builder::new()
            .name("mc-camera".into())
            .spawn(move || {
                let step = 1.0 / CAM_HZ;
                let mut next = t0_cam + Duration::from_secs_f64(step);
                let mut t_prev = 0.0f64;
                let mut ticks: u64 = 1;
                while !stop2.load(Ordering::Relaxed) {
                    let t = t0_cam.elapsed().as_secs_f64();
                    let pos = cursor_pos();
                    let btn = buttons();
                    // real interval, not the nominal step: the bake replays these
                    // exact timestamps, so both must integrate with the same dt
                    let mut dt = t - t_prev;
                    if dt < 1.0 / 1000.0 {
                        dt = 1.0 / 1000.0;
                    }
                    if dt > 1.0 / 25.0 {
                        dt = 1.0 / 25.0;
                    }
                    cam.tick(&s2, pos, dt);
                    t_prev = t;
                    ticks += 1;
                    let snap = cam.snapshot();
                    {
                        let mut g = shared.lock().unwrap();
                        g.pos = pos;
                        g.snap = snap;
                        g.btn = btn;
                        g.ticks = ticks;
                    }
                    let _ = writeln!(track, "{:.5},{},{},{}", t, pos.x as i32, pos.y as i32, btn);

                    let now = Instant::now();
                    if now < next {
                        std::thread::sleep(next - now);
                    }
                    next += Duration::from_secs_f64(step);
                    if Instant::now() > next + Duration::from_millis(100) {
                        next = Instant::now();
                    }
                }
            })
            .map_err(|e| format!("启动相机线程失败: {e}"))?;
    }

    let mut frame_buf = vec![0u32; (mon.w * mon.h) as usize];
    let mut crop_buf = vec![0u32; (out_w * out_h) as usize];
    let mut rs = Resampler::new();
    let mut rs_prev = Resampler::new();
    let mut prev_buf: Vec<u32> = Vec::new();
    let mut sprites = SpriteCache::new();

    let mut frames_csv: BufWriter<File> = BufWriter::new(
        OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(out_dir.join("frames.csv"))
            .map_err(|e| format!("创建 frames.csv 失败: {e}"))?,
    );
    let _ = writeln!(frames_csv, "# frame,camera_tick,cx,cy,w,h");

    let start = t0_shared;
    let frame_dur = 1.0 / fps as f64;
    let mut next = start + Duration::from_secs_f64(frame_dur);
    let mut emitted: i64 = 0;
    let mut written: i64 = 0;
    let mut written_pub: i64 = 0;
    let mut write_err: Option<String> = None;
    // A full disk is the most common way a long recording dies, and ffmpeg only
    // says so after the file is already damaged.
    if let Some(mb) = free_space_mb(out_dir) {
        if mb < 500 {
            return Err(format!("磁盘空间不足（剩余 {mb} MB）"));
        }
    }
    let mut dropped = 0u32;

    while !stop.load(Ordering::Relaxed) {
        if !cap.grab(&mut frame_buf) {
            dropped += 1;
            if dropped > 120 {
                break;
            }
            std::thread::sleep(Duration::from_millis(2));
            continue;
        }
        dropped = 0;

        let (pos, snap, ticks) = {
            let g = shared.lock().unwrap();
            (g.pos, g.snap, g.ticks)
        };

        if let Some(m) = master.as_mut() {
            if let Err(e) = m.write_frame(&frame_buf) {
                write_err = Some(format!("写入原片失败: {e}"));
                break;
            }
        }

        let mut r = rect_from_snapshot(&snap, mon);
        let mut lx = r.x - mon.x;
        let mut ly = r.y - mon.y;
        if lx < 0 {
            lx = 0;
        }
        if ly < 0 {
            ly = 0;
        }
        if lx + r.w > mon.w {
            r.w = mon.w - lx;
        }
        if ly + r.h > mon.h {
            r.h = mon.h - ly;
        }
        if r.w >= 4 && r.h >= 4 {
            crate::hud::set_frame(
                Some(crate::camera::IRect::new(r.x, r.y, r.w, r.h)),
                Some(cfg.mon),
                &format!("{}×{}", r.w, r.h),
            );
            rs.prep(lx as f32, ly as f32, r.w as f32, r.h as f32, out_w, out_h);
            rs.run(&frame_buf, mon.w, mon.h, &mut crop_buf, out_w);

            if let Some(spr) = sprites.get() {
                let sc = out_w as f32 / r.w as f32;
                // The viewport grows when the cursor moves fast, which shrinks
                // everything inside it - including the cursor. Scaling the sprite
                // by the same factor keeps it the size it has at rest, so it reads
                // as growing while the world pulls back.
                let grow = crate::camera::growth_factor(r.w as f32, out_w, s.zoom);
                draw(
                    &mut crop_buf,
                    out_w,
                    out_h,
                    (pos.x - r.x as f32) * sc,
                    (pos.y - r.y as f32) * sc,
                    sc * grow,
                    spr,
                );
            }
            if let Err(e) = camera.write_frame(&crop_buf) {
                write_err = Some(format!("写入跟拍成片失败: {e}"));
                break;
            }

            // ---- live preview (every 3rd frame ≈ 10 Hz)
            if let Some(sink) = &cfg.preview {
                written_pub += 1;
                if written_pub % 3 == 0 {
                    let pw = (1080u32.min(out_w as u32)) & !1;
                    let ph = (((pw as f32) * out_h as f32 / out_w as f32).round() as u32) & !1;
                    if pw >= 16 && ph >= 16 {
                        prev_buf.resize((pw * ph) as usize, 0);
                        rs_prev.prep(0.0, 0.0, out_w as f32, out_h as f32, pw as i32, ph as i32);
                        rs_prev.run(&crop_buf, out_w, out_h, &mut prev_buf, pw as i32);
                        if let Ok(mut g) = sink.lock() {
                            *g = Some(PreviewShot {
                                w: pw,
                                h: ph,
                                px: prev_buf.clone(),
                            });
                        }
                    }
                }
            }
        }

        let _ = writeln!(frames_csv, "{},{},{:.3},{:.3},{:.3},{:.3}", written, ticks, snap.center.x, snap.center.y, snap.src_w, snap.src_h);
        emitted += 1;
        written += 1;

        // CFR: duplicate until the frame count matches the wall clock
        let ideal = (start.elapsed().as_secs_f64() * fps as f64).floor() as i64;
        // A slept/timed-out loop must not try to catch up hours of frames: cap
        // the burst at two seconds and let the timeline record the gap.
        let catch_up_cap = emitted + (fps as i64) * 2;
        while emitted < ideal && emitted < catch_up_cap {
            let _ = writeln!(frames_csv, "{},{}", written, ticks);
            if let Some(m) = master.as_mut() {
                if let Err(e) = m.write_frame(&frame_buf) {
                    write_err = Some(format!("写入原片失败: {e}"));
                    break;
                }
            }
            if let Err(e) = camera.write_frame(&crop_buf) {
                write_err = Some(format!("写入跟拍成片失败: {e}"));
                break;
            }
            emitted += 1;
            written += 1;
        }

        if written % 300 == 0 && write_err.is_none() {
            if let Some(mb) = free_space_mb(out_dir) {
                if mb < 200 {
                    write_err = Some(format!("磁盘空间不足（剩余 {mb} MB）"));
                }
            }
        }
        if write_err.is_some() {
            break;
        }

        let now = Instant::now();
        if now < next {
            std::thread::sleep(next - now);
        }
        next += Duration::from_secs_f64(frame_dur);
        if Instant::now() > next + Duration::from_millis(200) {
            next = Instant::now();
        }
    }

    crate::hud::set_rect(None, "");
    let elapsed = start.elapsed().as_secs_f64();
    stop.store(true, Ordering::Relaxed); // camera thread
    std::thread::sleep(Duration::from_millis(20));
    drop(frames_csv);

    let master_code = master.map(|m| m.finish()).unwrap_or(0);
    let code = camera.finish();

    let mut failure = write_err;
    if failure.is_none() && master_code != 0 {
        failure = Some(format!("原片编码器异常退出 ({master_code})"));
    }
    if failure.is_none() && code != 0 {
        failure = Some(format!("跟拍编码器异常退出 ({code})"));
    }

    // Written either way: a folder without meta.json is invisible in the
    // library, so a failed take would silently vanish and be unrecoverable.
    let mut meta = meta_json(&cfg, elapsed, written);
    if failure.is_some() {
        meta = meta.replacen("  \"frames\":", "  \"complete\": false,\n  \"frames\":", 1);
    }
    if let Err(e) = std::fs::write(out_dir.join("meta.json"), &meta) {
        crate::mc_error!("rec", "写 meta.json 失败: {e}");
    }
    if let Some(why) = failure {
        return Err(format!("{why}（本次录制已中断，文件可能不完整）"));
    }

    Ok(RecSummary {
        frames: written as i32,
        duration: elapsed,
        out_dir: out_dir.to_path_buf(),
        dropped,
    })
}

/// Free space on the volume that holds `path`, in MB.
fn free_space_mb(path: &std::path::Path) -> Option<u64> {
    use windows::core::HSTRING;
    use windows::Win32::Storage::FileSystem::GetDiskFreeSpaceExW;
    let mut free = 0u64;
    let p = HSTRING::from(path.as_os_str().to_string_lossy().to_string());
    unsafe {
        let _ = GetDiskFreeSpaceExW(&p, Some(&mut free), None, None);
    }
    if free > 0 {
        Some(free / (1024 * 1024))
    } else {
        None
    }
}

/// Same rounding rules as `Camera::source_rect`, but taken from the snapshot the
/// camera thread published (so live and offline agree).
fn rect_from_snapshot(snap: &crate::camera::CamSnapshot, mon: IRect) -> IRect {
    let mut w = (snap.src_w.round() as i32).max(2) & !1;
    let mut h = (snap.src_h.round() as i32).max(2) & !1;
    if w > mon.w {
        w = mon.w & !1;
    }
    if h > mon.h {
        h = mon.h & !1;
    }
    let mut x = (snap.center.x - w as f32 * 0.5).round() as i32;
    let mut y = (snap.center.y - h as f32 * 0.5).round() as i32;
    if x < mon.x {
        x = mon.x;
    }
    if y < mon.y {
        y = mon.y;
    }
    if x + w > mon.right() {
        x = mon.right() - w;
    }
    if y + h > mon.bottom() {
        y = mon.bottom() - h;
    }
    IRect::new(x, y, w, h)
}
