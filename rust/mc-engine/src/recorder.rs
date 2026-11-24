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

/// Where the camera reads the pointer from.
///
/// `Scripted` and `Injected` exist so a recording can be exercised without
/// touching the machine's real pointer - which is the only way to test the
/// follow camera while somebody else is using the desktop.
#[derive(Clone)]
pub enum CursorSource {
    Real,
    /// A smooth path derived from the clock, with a fast segment so the
    /// speed-driven viewport gets exercised too.
    Scripted,
    /// Positions pushed from outside (tests drive this).
    Injected(Arc<std::sync::Mutex<Vec2>>),
}

/// Copy a rectangle out of a frame, row by row.
fn copy_rect(src: &[u32], stride: i32, x: i32, y: i32, w: i32, h: i32) -> Vec<u32> {
    let mut out = Vec::with_capacity((w * h) as usize);
    for row in 0..h {
        let s = ((y + row) * stride + x) as usize;
        out.extend_from_slice(&src[s..s + w as usize]);
    }
    out
}

/// Put a rectangle back, row by row.
fn paste_rect(dst: &mut [u32], stride: i32, x: i32, y: i32, w: i32, h: i32, data: &[u32]) {
    for row in 0..h {
        let d = ((y + row) * stride + x) as usize;
        let s = (row * w) as usize;
        dst[d..d + w as usize].copy_from_slice(&data[s..s + w as usize]);
    }
}

fn scripted_pos(mon: IRect, t: f64) -> Vec2 {
    let w = mon.w as f32;
    let h = mon.h as f32;
    let a = t as f32 * 5.0;
    Vec2::new(
        mon.x as f32 + w * (0.5 + 0.30 * a.cos()),
        mon.y as f32 + h * (0.5 + 0.28 * (a * 0.63).sin()),
    )
}

fn read_cursor(src: &CursorSource, mon: IRect, t: f64) -> Vec2 {
    match src {
        CursorSource::Real => cursor_pos(),
        CursorSource::Scripted => scripted_pos(mon, t),
        CursorSource::Injected(slot) => *slot.lock().unwrap_or_else(|e| e.into_inner()),
    }
}

/// What the recorder is doing right now, published for diagnostics.
///
/// Without this, answering "why was that take slow" means adding a log line and
/// rebuilding; the numbers are already here, they just had nowhere to go.
#[derive(Default)]
pub struct FrameStats {
    pub frames: i64,
    pub dropped: u32,
    pub last_ms: f32,
    pub p95_ms: f32,
    pub expand: f32,
    pub speed: f32,
    pub center: [f32; 2],
    pub src: [f32; 2],
    /// Where the frame time goes, so an optimisation can target the real cost.
    pub grab_ms: f32,
    pub master_ms: f32,
    pub resample_ms: f32,
    pub camera_ms: f32,
    pub write_ms: f32,
    recent: std::collections::VecDeque<f32>,
}

/// A copy without the per-frame ring, which is what callers actually need.
#[derive(Default, Clone, Copy)]
pub struct StatsSnapshot {
    pub frames: i64,
    pub grab_ms: f32,
    pub master_ms: f32,
    pub resample_ms: f32,
    pub camera_ms: f32,
    pub write_ms: f32,
    pub dropped: u32,
    pub last_ms: f32,
    pub p95_ms: f32,
    pub expand: f32,
    pub speed: f32,
    pub center: [f32; 2],
    pub src: [f32; 2],
}

impl FrameStats {
    pub fn clone_stats(&self) -> StatsSnapshot {
        StatsSnapshot {
            frames: self.frames,
            grab_ms: self.grab_ms,
            master_ms: self.master_ms,
            camera_ms: self.camera_ms,
            resample_ms: self.resample_ms,
            write_ms: self.write_ms,
            dropped: self.dropped,
            last_ms: self.last_ms,
            p95_ms: self.p95_ms,
            expand: self.expand,
            speed: self.speed,
            center: self.center,
            src: self.src,
        }
    }
}

pub type DebugSink = Arc<std::sync::Mutex<FrameStats>>;

pub fn new_debug_sink() -> DebugSink {
    Arc::new(std::sync::Mutex::new(FrameStats::default()))
}

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
    /// capture the desktop's own sound (WASAPI loopback)
    pub audio_system: bool,
    /// capture the microphone
    pub audio_mic: bool,
    /// optional live preview output (the recorder is the only owner of the
    /// DXGI duplication, so it has to publish frames itself)
    pub preview: Option<PreviewSink>,
    /// optional live telemetry
    pub debug: Option<DebugSink>,
    /// generate frames instead of reading the desktop (tests only)
    pub synthetic: bool,
    /// where the follow camera reads the pointer from
    pub cursor: CursorSource,
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
            audio_system: false,
            audio_mic: false,
            preview: None,
            debug: None,
            synthetic: false,
            cursor: CursorSource::Real,
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


fn meta_json(cfg: &RecorderConfig, duration: f64, frames: i64, dropped: u32) -> String {
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
            "  \"deadZone\": {:.4},\n",
            "  \"cursorSmoothMs\": {:.1},\n",
            "  \"clickRing\": {},\n",
            // duration/frames are recorded here so loaders never have to probe
            // the file with ffmpeg to find out how long the clip is
            "  \"duration\": {:.6},\n",
            "  \"dropped\": {},\n",
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
        s.dead_zone,
        s.cursor_smooth_ms,
        if s.click_ring { 1 } else { 0 },
        duration,
        dropped,
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
        let cap = if cfg.synthetic {
            Capture::open_synthetic(cfg.mon)?
        } else {
            Capture::open(cfg.mon)?
        };

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
    {
        // Say it out loud: on a small screen the requested zoom is not what the
        // take will actually show, and that is invisible until playback.
        let (rw, rh) = crate::camera::requested_viewport(&s);
        let (aw, ah, limited) = crate::camera::fit_viewport(&s, mon);
        if limited {
            crate::mc_warn!(
                "camera",
                "屏幕 {}x{} 放不下 {:.0}x{:.0} 的视口，实际限制为 {:.0}x{:.0}（有效缩放 {:.2}×）",
                mon.w, mon.h, rw, rh, aw, ah,
                s.out_width as f32 / aw.max(1.0)
            );
        }
    }

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

    // Started together with the clock, once the encoders are warm: the two
    // pre-roll frames are not part of the timeline, so audio started earlier
    // would sit a couple of hundred milliseconds ahead of the picture.
    let mut audio: Option<crate::audio::AudioSession> = None;

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
    //
    // It starts only once the first frame has actually reached both encoders:
    // the first write costs a couple of hundred milliseconds while ffmpeg fills
    // its pipe, and a clock started before that has to duplicate frames to stay
    // in sync with the wall clock - which freezes the opening of every take.
    let mut t0_shared = Instant::now();
    let shared = Arc::new(std::sync::Mutex::new(CamShared {
        pos: read_cursor(&cfg.cursor, mon, 0.0),
        snap: Default::default(),
        btn: 0,
        ticks: 1, // the seed tick
    }));

    // Seed the framing so frame 0 already has a sensible rectangle.
    {
        let mut cam = Camera::new();
        cam.set_screen(mon);
        let start_pos = read_cursor(&cfg.cursor, mon, 0.0);
        cam.reset(start_pos);
        cam.tick(&s, start_pos, 1.0 / CAM_HZ);
        let mut g = shared.lock().unwrap();
        g.pos = start_pos;
        g.snap = cam.snapshot();
    }

    // Spawned lazily, together with the clock, so the trace and the video share
    // their origin no matter how long the encoders take to warm up.
    // The camera thread owns `track.csv`; joining it is what guarantees the
    // trace is on disk before anything reads the take back.
    let cam_handle: std::sync::Arc<std::sync::Mutex<Option<std::thread::JoinHandle<()>>>> =
        std::sync::Arc::new(std::sync::Mutex::new(None));
    let mut spawn_camera: Option<Box<dyn FnOnce(Instant) + Send>> = {
        let shared = shared.clone();
        let cam_slot = cam_handle.clone();
        let s2 = s.clone();
        let stop2 = stop.clone();
        let cursor = cfg.cursor.clone();
        Some(Box::new(move |t0_cam: Instant| {
                let cursor_src = cursor.clone();
            let spawned = std::thread::Builder::new()
                .name("mc-camera".into())
                .spawn(move || {
                    let mut cam = Camera::new();
                    cam.set_screen(mon);
                    cam.reset(read_cursor(&cursor_src, mon, 0.0));
                    let step = 1.0 / CAM_HZ;
                    let mut next = t0_cam + Duration::from_secs_f64(step);
                    let mut t_prev = 0.0f64;
                    let mut ticks: u64 = 1;
                    while !stop2.load(Ordering::Relaxed) {
                        let t = t0_cam.elapsed().as_secs_f64();
                        let pos = read_cursor(&cursor_src, mon, t);
                        let btn = buttons();
                        // real interval, not the nominal step: the bake replays
                        // these exact timestamps, so both must integrate the same dt
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
                });
            match spawned {
                Ok(h) => {
                    if let Ok(mut slot) = cam_slot.lock() {
                        *slot = Some(h);
                    }
                }
                Err(e) => crate::mc_error!("rec", "启动相机线程失败: {e}"),
            }
        }))
    };

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

    let mut clock_started = false;
    let frame_dur = 1.0 / fps as f64;
    let mut next = Instant::now();
    let mut emitted: i64 = 0;
    let mut written: i64 = 0;
    let mut written_pub: i64 = 0;
    let mut write_err: Option<String> = None;
    // Set when the capture side dies. Carried into `failure` so the take reports
    // itself as broken instead of ending quietly after four seconds.
    let mut capture_dead: Option<String> = None;
    // A full disk is the most common way a long recording dies, and ffmpeg only
    // says so after the file is already damaged.
    if let Some(mb) = free_space_mb(out_dir) {
        if mb < 500 {
            return Err(format!("磁盘空间不足（剩余 {mb} MB）"));
        }
    }
    let mut dropped = 0u32;
    let mut dropped_total = 0u32;

    while !stop.load(Ordering::Relaxed) {
        let frame_t0 = Instant::now();
        if !cap.grab(&mut frame_buf) {
            dropped += 1;
            if let Some(code) = cap.format_problem() {
                capture_dead = Some(format!(
                    "显示器色彩格式不受支持（HDR 或 10bit，format=0x{code:X}），请在 Windows 设置中关闭 HDR 后重试"
                ));
                break;
            }
            if dropped > 120 {
                capture_dead = Some(
                    "连续 4 秒没有取到新画面（显示器切换、分辨率变化，或采集被其他程序占用）".into(),
                );
                break;
            }
            std::thread::sleep(Duration::from_millis(2));
            continue;
        }
        dropped_total += dropped;
        dropped = 0;
        let mut stage_grab = frame_t0.elapsed().as_secs_f64() as f32 * 1000.0;
        let mut stage_resample = 0.0f32;
        let mut stage_master = 0.0f32;
        let mut stage_draw = 0.0f32;
        let mut stage_camera = 0.0f32;

        let (pos, snap, ticks) = {
            let g = shared.lock().unwrap();
            (g.pos, g.snap, g.ticks)
        };

        // Desktop Duplication never includes the pointer, so the master take has
        // to have it painted in. The pixels underneath are saved first and put
        // back after the write: the follow camera crops from a clean frame and
        // draws its own sprite, kept crisp and at a constant apparent size.
        let mut under: Option<(i32, i32, i32, i32, Vec<u32>)> = None;
        if master.is_some() {
            if let Some(spr) = sprites.get() {
            let cx = pos.x - mon.x as f32;
            let cy = pos.y - mon.y as f32;
            let (bx, by, bw, bh) = crate::cursor::sprite_bounds(cx, cy, 1.0, spr, mon.w, mon.h);
            if bw > 0 && bh > 0 {
                let saved = copy_rect(&frame_buf, mon.w, bx, by, bw, bh);
                draw(&mut frame_buf, mon.w, mon.h, cx, cy, 1.0, spr);
                under = Some((bx, by, bw, bh, saved));
            }
            }
        }

        if let Some(m) = master.as_mut() {
            if let Err(e) = m.write_frame(&frame_buf) {
                write_err = Some(format!("写入原片失败: {e}"));
                break;
            }
        stage_master = frame_t0.elapsed().as_secs_f64() as f32 * 1000.0 - stage_grab;
        }
        if let Some((bx, by, bw, bh, saved)) = under.take() {
            paste_rect(&mut frame_buf, mon.w, bx, by, bw, bh, &saved);
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
            stage_resample = frame_t0.elapsed().as_secs_f64() as f32 * 1000.0 - stage_grab - stage_master;

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
            stage_draw = frame_t0.elapsed().as_secs_f64() as f32 * 1000.0 - stage_grab - stage_master - stage_resample;
            if let Err(e) = camera.write_frame(&crop_buf) {
                write_err = Some(format!("写入跟拍成片失败: {e}"));
                break;
            }
            stage_camera = frame_t0.elapsed().as_secs_f64() as f32 * 1000.0 - stage_grab - stage_master - stage_resample - stage_draw;

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

        // Frame 0 has now reached both encoders: the warm-up is behind us, so
        // this is where the timeline and the camera trace really begin.
        // Two frames, not one: the *second* pipe write is the expensive one, so a
        // clock started after frame 0 still has to duplicate a handful of frames.
        if !clock_started && written >= 1 {
            clock_started = true;
            t0_shared = Instant::now();
            next = t0_shared + Duration::from_secs_f64(frame_dur);
            if let Some(spawn) = spawn_camera.take() {
                spawn(t0_shared);
            }
            audio = crate::audio::start(out_dir, cfg.audio_system, cfg.audio_mic);
            crate::mc_info!("rec", "计时从首帧写出后开始");
        }

        let _ = writeln!(frames_csv, "{},{},{:.3},{:.3},{:.3},{:.3}", written, ticks, snap.center.x, snap.center.y, snap.src_w, snap.src_h);
        if let Some(sink) = &cfg.debug {
            if let Ok(mut d) = sink.lock() {
                d.frames = written;
                d.dropped = dropped_total;
                let ms = frame_t0.elapsed().as_secs_f64() as f32 * 1000.0;
                d.last_ms = ms;
                d.recent.push_back(ms);
                while d.recent.len() > 120 {
                    d.recent.pop_front();
                }
                let mut v: Vec<f32> = d.recent.iter().copied().collect();
                v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
                if !v.is_empty() {
                    d.p95_ms = v[((v.len() as f32 * 0.95) as usize).min(v.len() - 1)];
                }
                d.grab_ms = stage_grab;
                d.master_ms = stage_master;
        d.resample_ms = stage_resample;
        d.write_ms = stage_draw;
                    d.camera_ms = stage_camera;
        d.expand = snap.expand;
                d.speed = snap.speed;
                d.center = [snap.center.x, snap.center.y];
                d.src = [snap.src_w, snap.src_h];
            }
        }
        emitted += 1;
        written += 1;

        // CFR: duplicate until the frame count matches the wall clock
        let ideal = (t0_shared.elapsed().as_secs_f64() * fps as f64).floor() as i64;
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
    let elapsed = t0_shared.elapsed().as_secs_f64();
    stop.store(true, Ordering::Relaxed); // camera thread
    // Waiting for it actually to finish, rather than hoping 20 ms was enough:
    // the track buffer is flushed when the thread exits, and a partial
    // track.csv is the one thing that cannot be reconstructed later.
    if let Ok(mut slot) = cam_handle.lock() {
        if let Some(h) = slot.take() {
            let _ = h.join();
        }
    }
    drop(frames_csv);

    let (master_code, master_err) = master.map(|m| m.finish()).unwrap_or((0, String::new()));
    let (code, camera_err) = camera.finish();

    // Audio is folded in after the encoders have closed their files, so a
    // failed mux leaves a perfectly good silent video rather than a broken one.
    let audio_files = match audio {
        Some(session) => session.stop(),
        None => Vec::new(),
    };
    let usable: Vec<std::path::PathBuf> = audio_files
        .iter()
        .filter(|f| f.usable())
        .map(|f| f.path.clone())
        .collect();
    for f in audio_files.iter().filter(|f| !f.usable()) {
        if let Some(e) = &f.error {
            crate::mc_warn!("audio", "{} 没有可用音频: {e}", f.path.display());
        }
    }
    if !usable.is_empty() {
        let ff = ffmpeg.clone();
        for name in ["master.mp4", "camera.mp4"] {
            let video = out_dir.join(name);
            match crate::ffmpeg::mux_audio(&ff, &video, &usable, 0.0, None, None) {
                Ok(()) => crate::mc_info!("audio", "{name} 已加入 {} 条音轨", usable.len()),
                Err(e) => {
                    crate::mc_warn!("audio", "{name} 封装音频失败: {e}");
                }
            }
        }
    }

    let mut failure = write_err.or(capture_dead);
    if failure.is_none() && master_code != 0 {
        failure = Some(format!("原片编码器异常退出 ({master_code}) {master_err}"));
    }
    if failure.is_none() && code != 0 {
        failure = Some(format!("跟拍编码器异常退出 ({code}) {camera_err}"));
    }

    // Written either way: a folder without meta.json is invisible in the
    // library, so a failed take would silently vanish and be unrecoverable.
    let mut meta = meta_json(&cfg, elapsed, written, dropped_total);
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
pub fn free_space_mb(path: &std::path::Path) -> Option<u64> {
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
