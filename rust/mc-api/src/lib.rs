//! Command layer shared by the Tauri shell and the local HTTP demo server.
//! Both transports expose the same six operations, so the front-end is
//! transport-agnostic.

use base64::Engine as _;
use mc_engine::clip::{find_ffmpeg, load_clip, settings_from_meta};
use mc_engine::cursor::{arrow_sprite, draw as draw_cursor};
use mc_engine::edit::parse_edit;
use mc_engine::ffmpeg::FrameReader;
use mc_engine::render::{bake_path, frame_src_rect};
use mc_engine::resample::Resampler;
use mc_engine::Settings;
use serde::Serialize;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

#[derive(Serialize, Clone)]
pub struct ClipDto {
    pub dir: String,
    pub name: String,
    pub fps: i32,
    pub frames: i32,
    pub duration: f64,
    pub mon_x: i32,
    pub mon_y: i32,
    pub mon_w: i32,
    pub mon_h: i32,
}

#[derive(Serialize)]
pub struct BakeDto {
    pub frames: i32,
    pub fps: i32,
    pub duration: f64,
    pub mon: [i32; 4],
    pub path: Vec<[f32; 4]>,
    pub ticks: Vec<u32>,
}

/// Where recordings are written. Order:
///   1. `MC_CAPTURES` (developer override)
///   2. the folder chosen in the settings dialog
///   3. the user's Videos library
///   4. `%LOCALAPPDATA%\MouseCam\captures` if the above is not writable
pub fn captures_root() -> PathBuf {
    let mut g = captures_root_cache().lock().unwrap();
    if let Some(p) = g.as_ref() {
        return p.clone();
    }
    let resolved = resolve_captures_root();
    *g = Some(resolved.clone());
    resolved
}

static CAPTURES_ROOT: std::sync::OnceLock<std::sync::Mutex<Option<PathBuf>>> = std::sync::OnceLock::new();

fn captures_root_cache() -> &'static std::sync::Mutex<Option<PathBuf>> {
    CAPTURES_ROOT.get_or_init(|| std::sync::Mutex::new(None))
}

fn invalidate_captures_root() {
    if let Some(m) = CAPTURES_ROOT.get() {
        *m.lock().unwrap() = None;
    }
}

/// Picks the first folder that can actually hold a recording.
///
/// The configured path is only a preference: on a machine where security software
/// blocks an unsigned executable from creating folders outside its own, every
/// write under the user profile fails with "access denied" and the recorder would
/// otherwise refuse to start with no way forward.
fn resolve_captures_root() -> PathBuf {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Some(dir) = settings().captures_dir.filter(|d| !d.trim().is_empty()) {
        candidates.push(PathBuf::from(dir));
    }
    candidates.push(default_captures_dir());
    candidates.push(local_app_dir().join("captures"));
    candidates.push(std::env::temp_dir().join("MouseCam").join("captures"));
    if let Ok(exe) = std::env::current_exe() {
        if let Some(d) = exe.parent() {
            candidates.push(d.join("captures"));
        }
    }

    let first = candidates.first().cloned();
    for c in &candidates {
        if std::fs::create_dir_all(c).is_ok() && writable(c) {
            if Some(c) != first.as_ref() {
                mc_engine::mc_warn!(
                    "captures",
                    "{} is not writable, using {} instead",
                    first.map(|p| p.display().to_string()).unwrap_or_default(),
                    c.display()
                );
            }
            return c.clone();
        }
    }
    mc_engine::mc_error!("captures", "no writable capture folder among {} candidates", candidates.len());
    candidates
        .into_iter()
        .next()
        .unwrap_or_else(|| PathBuf::from("captures"))
}

fn default_captures_dir() -> PathBuf {
    if let Ok(d) = std::env::var("MC_CAPTURES") {
        if !d.trim().is_empty() {
            return PathBuf::from(d);
        }
    }
    match videos_dir() {
        Some(v) => v.join("MouseCam"),
        None => local_app_dir().join("captures"),
    }
}

fn writable(dir: &std::path::Path) -> bool {
    let probe = dir.join(".mc_write_test");
    match std::fs::write(&probe, b"x") {
        Ok(_) => {
            let _ = std::fs::remove_file(&probe);
            true
        }
        Err(_) => false,
    }
}

fn local_app_dir() -> PathBuf {
    for k in ["LOCALAPPDATA", "USERPROFILE"] {
        if let Ok(v) = std::env::var(k) {
            if !v.trim().is_empty() {
                return PathBuf::from(v).join("MouseCam");
            }
        }
    }
    PathBuf::from("MouseCam")
}

/// The user's Videos library via `SHGetKnownFolderPath`.
fn videos_dir() -> Option<PathBuf> {
    use windows::Win32::System::Com::CoTaskMemFree;
    use windows::Win32::UI::Shell::{FOLDERID_Videos, SHGetKnownFolderPath, KF_FLAG_DEFAULT};
    unsafe {
        let p = SHGetKnownFolderPath(&FOLDERID_Videos, KF_FLAG_DEFAULT, None).ok()?;
        let s = p.to_string().ok();
        CoTaskMemFree(Some(p.0 as *const _));
        let s = s?;
        if s.is_empty() {
            return None;
        }
        Some(PathBuf::from(s))
    }
}

// ---------------------------------------------------------------- settings
//
// Line based, like `.mcl`: `key=value`, `#` comments. No extra dependency and
// it stays readable if someone has to fix it by hand.

#[derive(Clone, Default)]
pub struct AppSettings {
    pub captures_dir: Option<String>,
    pub hw_encode: bool,
    pub hud_default: bool,
    pub verbose: bool,
}

fn settings_file() -> PathBuf {
    // MC_SETTINGS lets a portable copy keep its settings next to the binary
    // (and lets the test harness point it at a writable folder).
    if let Ok(p) = std::env::var("MC_SETTINGS") {
        if !p.trim().is_empty() {
            return PathBuf::from(p);
        }
    }
    local_app_dir().join("settings.ini")
}

fn settings_cell() -> &'static Mutex<Option<AppSettings>> {
    static CACHE: OnceLock<Mutex<Option<AppSettings>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(None))
}

pub fn settings() -> AppSettings {
    let mut g = settings_cell().lock().unwrap();
    if let Some(s) = g.as_ref() {
        return s.clone();
    }
    let mut out = AppSettings {
        captures_dir: None,
        hw_encode: true,
        hud_default: true,
        // A debug build exists to be diagnosed, so log everything by default.
        verbose: cfg!(debug_assertions),
    };
    if let Ok(txt) = std::fs::read_to_string(settings_file()) {
        for line in txt.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let Some((k, v)) = line.split_once('=') else {
                continue;
            };
            let v = v.trim();
            match k.trim() {
                "captures" if !v.is_empty() => out.captures_dir = Some(v.to_string()),
                "hw" => out.hw_encode = v == "1" || v.eq_ignore_ascii_case("true"),
                "hud" => out.hud_default = v == "1" || v.eq_ignore_ascii_case("true"),
                "verbose" => out.verbose = v == "1" || v.eq_ignore_ascii_case("true"),
                _ => {}
            }
        }
    }
    *g = Some(out.clone());
    out
}

pub fn set_settings(captures_dir: String, hw: bool, hud: bool, verbose: bool) -> Result<(), String> {
    let dir = captures_dir.trim().to_string();
    let path = settings_file();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("创建配置目录失败: {e}"))?;
    }
    let body = format!(
        "# MouseCam 设置\ncaptures={}\nhw={}\nhud={}\nverbose={}\n",
        dir,
        if hw { 1 } else { 0 },
        if hud { 1 } else { 0 },
        if verbose { 1 } else { 0 }
    );
    std::fs::write(&path, body).map_err(|e| format!("写入配置失败: {e}"))?;
    *settings_cell().lock().unwrap() = None;
    // the capture folders depend on the setting, so resolve them again
    invalidate_captures_root();
    Ok(())
}

/// Opens a folder in Explorer.
pub fn open_folder(dir: String) -> Result<(), String> {
    let p = std::path::PathBuf::from(dir.trim());
    if p.as_os_str().is_empty() {
        return Err("没有可打开的文件夹".into());
    }
    std::fs::create_dir_all(&p).map_err(|e| format!("无法创建文件夹: {e}"))?;
    if !p.is_dir() {
        return Err(format!("不是文件夹: {}", p.display()));
    }
    if shell_open(&p).is_ok() {
        return Ok(());
    }
    // The shell refused (a restricted desktop does this) - a second copy of
    // explorer.exe would fail to initialise with 0xc0000142, so hand the user the
    // path instead of a dead button.
    if copy_to_clipboard(&p.as_os_str().to_string_lossy()) {
        return Err("无法打开文件夹，路径已复制到剪贴板".into());
    }
    Err("无法打开文件夹".into())
}

/// Puts text on the clipboard, used when the shell will not open a window.
fn copy_to_clipboard(text: &str) -> bool {
    use windows::Win32::Foundation::HANDLE;
    use windows::Win32::System::DataExchange::{
        CloseClipboard, EmptyClipboard, OpenClipboard, SetClipboardData,
    };
    use windows::Win32::System::Memory::{GlobalAlloc, GlobalLock, GlobalUnlock, GMEM_MOVEABLE};
    const CF_UNICODETEXT: u32 = 13;
    unsafe {
        let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
        let bytes = wide.len() * std::mem::size_of::<u16>();
        let h = match GlobalAlloc(GMEM_MOVEABLE, bytes) {
            Ok(h) => h,
            Err(_) => return false,
        };
        let dst = GlobalLock(h);
        if dst.is_null() {
            return false;
        }
        std::ptr::copy_nonoverlapping(wide.as_ptr() as *const u8, dst as *mut u8, bytes);
        let _ = GlobalUnlock(h);
        if OpenClipboard(None).is_err() {
            return false;
        }
        let _ = EmptyClipboard();
        // on success the clipboard owns the memory, so it must not be freed here
        let ok = SetClipboardData(CF_UNICODETEXT, Some(HANDLE(h.0))).is_ok();
        let _ = CloseClipboard();
        ok
    }
}

/// Asks the running shell to open a folder.
///
/// Spawning `explorer.exe` ourselves put a second copy of the shell on screen and
/// on some systems that copy fails to initialise (0xc0000142, "the application
/// was unable to start correctly"). `ShellExecute` hands the request to the shell
/// that is already running.
fn shell_open(p: &std::path::Path) -> Result<(), String> {
    use windows::core::HSTRING;
    use windows::Win32::UI::Shell::ShellExecuteW;
    use windows::Win32::UI::WindowsAndMessaging::SW_SHOWNORMAL;
    unsafe {
        let op = HSTRING::from("open");
        let file = HSTRING::from(p.as_os_str().to_string_lossy().to_string());
        let r = ShellExecuteW(None, &op, &file, None, None, SW_SHOWNORMAL);
        // an HINSTANCE of 32 or below is an error code, not a handle
        if r.0 as isize <= 32 {
            return Err(format!("无法打开文件夹 (code {})", r.0 as isize));
        }
    }
    Ok(())
}

/// Opens the folder that holds the file. The shell cannot be asked to select a
/// file without COM plumbing, and opening the folder is what makes the log easy
/// to find.
pub fn reveal_file(path: String) -> Result<(), String> {
    let p = std::path::PathBuf::from(path.trim());
    if !p.exists() {
        return Err(format!("文件不存在: {}", p.display()));
    }
    let opened = match p.parent() {
        Some(dir) => shell_open(dir),
        None => shell_open(&p),
    };
    if opened.is_ok() {
        return Ok(());
    }
    if copy_to_clipboard(&p.as_os_str().to_string_lossy()) {
        return Err("无法打开文件夹，路径已复制到剪贴板".into());
    }
    Err("无法打开文件夹".into())
}

fn clip_dto(dir: &PathBuf) -> Option<ClipDto> {
    let clip = load_clip(dir).ok()?;
    Some(ClipDto {
        dir: dir.display().to_string(),
        name: dir
            .file_name()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_default(),
        fps: clip.fps,
        frames: clip.frame_count,
        duration: clip.duration,
        mon_x: clip.mon.x,
        mon_y: clip.mon.y,
        mon_w: clip.mon.w,
        mon_h: clip.mon.h,
    })
}

pub fn list_clips() -> Vec<ClipDto> {
    let root = captures_root();
    let mut out = Vec::new();
    if let Ok(rd) = std::fs::read_dir(&root) {
        for e in rd.flatten() {
            let p = e.path();
            if !p.is_dir() {
                continue;
            }
            let name = p.file_name().map(|s| s.to_string_lossy().to_string());
            if !name.as_deref().unwrap_or("").starts_with("rec_") {
                continue;
            }
            if let Some(dto) = clip_dto(&p) {
                out.push(dto);
            }
        }
    }
    out.sort_by(|a, b| b.name.cmp(&a.name));
    out
}

pub fn open_clip(dir: String) -> Result<ClipDto, String> {
    clip_dto(&PathBuf::from(dir)).ok_or_else(|| "无法打开该素材".to_string())
}

fn build_settings(dir: &str, edit_text: &str) -> Result<(Settings, mc_engine::EditList), String> {
    let mut s = settings_from_meta(std::path::Path::new(dir))?;
    let edit = parse_edit(edit_text);
    edit.cam.apply(&mut s);
    Ok((s, edit))
}

pub fn api_bake(dir: String, edit: String) -> Result<BakeDto, String> {
    let clip = load_clip(std::path::Path::new(&dir))?;
    let (s, e) = build_settings(&dir, &edit)?;
    let (path, _ms) = bake_path(&clip, &s, &e);
    Ok(BakeDto {
        frames: clip.frame_count,
        fps: clip.fps,
        duration: clip.duration,
        mon: [clip.mon.x, clip.mon.y, clip.mon.w, clip.mon.h],
        path: path.iter().map(|f| [f.cx, f.cy, f.w, f.h]).collect(),
        ticks: clip.frame_ticks.clone(),
    })
}

pub fn track_points(dir: String) -> Result<Vec<Vec<f32>>, String> {
    let clip = load_clip(std::path::Path::new(&dir))?;
    let step = (clip.track.len() / 3000).max(1);
    Ok(clip
        .track
        .iter()
        .step_by(step)
        .map(|p| vec![p.t as f32, p.x as f32, p.y as f32])
        .collect())
}

fn encode_jpeg_bytes(bgra: &[u32], w: u32, h: u32, quality: u8) -> Result<Vec<u8>, String> {
    // The buffer is BGRA (D3D11 B8G8R8A8 / ffmpeg `-pix_fmt bgra`), which as a
    // little-endian u32 is 0xAARRGGBB: the LOW byte is blue and the HIGH byte is
    // red. Pushing low-to-high gave a red/blue swap in every still and preview.
    let mut rgb = Vec::with_capacity((w as usize) * (h as usize) * 3);
    for &p in bgra {
        rgb.push(((p >> 16) & 0xFF) as u8); // R
        rgb.push(((p >> 8) & 0xFF) as u8);  // G
        rgb.push((p & 0xFF) as u8);         // B
    }
    let mut out = std::io::Cursor::new(Vec::new());
    let mut enc = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut out, quality);
    enc.encode(&rgb, w, h, image::ExtendedColorType::Rgb8)
        .map_err(|e| format!("JPEG 编码失败: {e}"))?;
    Ok(out.into_inner())
}

fn encode_jpeg(bgra: &[u32], w: u32, h: u32, quality: u8) -> Result<String, String> {
    let bytes = encode_jpeg_bytes(bgra, w, h, quality)?;
    Ok(format!(
        "data:image/jpeg;base64,{}",
        base64::engine::general_purpose::STANDARD.encode(bytes)
    ))
}

fn preview_shot() -> Result<mc_engine::recorder::PreviewShot, String> {
    let from_rec = {
        let g = session().lock().unwrap();
        g.as_ref()
            .and_then(|s| s.sink.lock().ok().and_then(|x| x.clone()))
    };
    match from_rec {
        Some(s) => Ok(s),
        None => {
            let g = preview().lock().unwrap();
            g.as_ref()
                .and_then(|e| e.sink.lock().ok().and_then(|x| x.clone()))
                .ok_or_else(|| "预览尚未就绪".to_string())
        }
    }
}

/// Writes the preview frame to a file and returns its path. Shipping a 60 KB
/// base64 string through the IPC channel ten times a second is what an
/// equivalent recorder (Cap) avoids: the webview can load a file itself, so the
/// transport carries a path instead of the picture. Two names are alternated so
/// the browser cannot serve a cached copy.
pub fn preview_frame_path() -> Result<String, String> {
    let shot = preview_shot()?;
    let bytes = encode_jpeg_bytes(&shot.px, shot.w, shot.h, 82)?;
    static TICK: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
    let n = TICK.fetch_add(1, std::sync::atomic::Ordering::Relaxed) & 1;
    // Under the captures root: that folder is known to be writable (recordings
    // go there) and it is already inside the asset protocol scope. %TEMP% is
    // not guaranteed to exist as a usable directory.
    let dir = captures_root().join(".preview");
    std::fs::create_dir_all(&dir).map_err(|e| format!("创建预览目录失败: {e}"))?;
    let path = dir.join(format!("preview-{n}.jpg"));
    std::fs::write(&path, &bytes).map_err(|e| format!("写入预览失败: {e}"))?;
    Ok(path.display().to_string())
}

pub fn still(dir: String, edit: String, frame: i32, max_w: u32, kind: String) -> Result<String, String> {
    let clip = load_clip(std::path::Path::new(&dir))?;
    let ff = find_ffmpeg().ok_or("找不到 ffmpeg.exe")?;
    let (s, e) = build_settings(&dir, &edit)?;
    let (path, _) = bake_path(&clip, &s, &e);

    let frame = frame.clamp(0, (clip.frame_count - 1).max(0));
    let t = frame as f64 / clip.fps as f64;

    let mon = clip.mon;
    // Decode only as much as this request can use: a full 2560x1440 frame is
    // ~14.7 MB through the pipe and dominates the cost of a single still.
    let frect = frame_src_rect(&path[frame as usize], mon);
    let (dec_w, dec_h) = still_decode_size(&mon, &kind, &frect, max_w);
    let k = dec_w as f32 / mon.w as f32;

    let mut rd = FrameReader::open_scaled(
        &ff,
        &clip.master,
        Some(t),
        dec_w,
        dec_h,
        Some((dec_w, dec_h)),
    )
        .map_err(|e| format!("解码失败: {e}"))?;
    let mut src = vec![0u32; (dec_w * dec_h) as usize];
    if !rd.read_frame(&mut src) {
        return Err("无法解码该帧".into());
    }

    let mut rs = Resampler::new();

    if kind == "crop" {
        let r = frect;
        let lx = ((r.x - mon.x).max(0) as f32) * k;
        let ly = ((r.y - mon.y).max(0) as f32) * k;
        let rw = (r.w.min(mon.w).max(4) as f32) * k;
        let rh = (r.h.min(mon.h).max(4) as f32) * k;

        let out_w = max_w.min((rw / k) as u32).max(16) & !1;
        let out_h = ((out_w as f32 * rh / rw).round() as u32).max(16) & !1;

        let mut dst = vec![0u32; (out_w * out_h) as usize];
        rs.prep(lx, ly, rw, rh, out_w as i32, out_h as i32);
        rs.run(&src, dec_w, dec_h, &mut dst, out_w as i32);

        if let Some(spr) = arrow_sprite() {
            let p = mc_engine::edit::cursor_at(&clip.track, &e, t);
            let sc = out_w as f32 / rw;
            draw_cursor(&mut dst, out_w as i32, out_h as i32, (p.x - r.x as f32) * sc, (p.y - r.y as f32) * sc, sc, &spr);
        }
        encode_jpeg(&dst, out_w, out_h, 84)
    } else {
        let out_w = max_w.min(mon.w as u32).max(16) & !1;
        let out_h = ((out_w as f32 * mon.h as f32 / mon.w as f32).round() as u32).max(16) & !1;
        let mut dst = vec![0u32; (out_w * out_h) as usize];
        rs.prep(0.0, 0.0, dec_w as f32, dec_h as f32, out_w as i32, out_h as i32);
        rs.run(&src, dec_w, dec_h, &mut dst, out_w as i32);
        encode_jpeg(&dst, out_w, out_h, 82)
    }
}

pub fn export(
    dir: String,
    edit: String,
    out: String,
    format: Option<String>,
    quality: Option<i32>,
    width: Option<i32>,
    fps: Option<i32>,
) -> Result<String, String> {
    mc_engine::mc_info!("export", "{} -> {} format={:?}", dir, out, format);
    let clip = load_clip(std::path::Path::new(&dir))?;
    let ff = find_ffmpeg().ok_or("找不到 ffmpeg.exe")?;
    let (mut s, e) = build_settings(&dir, &edit)?;

    let fmt = mc_engine::ffmpeg::VideoFormat::parse(&format.unwrap_or_default());
    let crf = quality.unwrap_or(18).clamp(8, 40);
    if let Some(w) = width {
        if w >= 64 {
            s.out_width = w as i32;
        }
    }
    if let Some(f) = fps {
        if f >= 5 {
            s.fps = f;
        }
    }

    let out_path = if out.is_empty() {
        PathBuf::from(&dir).join(format!("export.{}", fmt.extension()))
    } else {
        PathBuf::from(out)
    };
    let sum = mc_engine::render_clip(
        &clip,
        &ff,
        &out_path,
        &s,
        &e,
        fmt,
        crf,
        |_, _| {},
    )?;
    Ok(format!(
        "{}  ({} 帧 / {:.1}s)",
        sum.out_path.display(),
        sum.frames,
        sum.duration
    ))
}


// ============================================================
//  Live recording
// ============================================================

struct Session {
    rec: mc_engine::Recorder,
    root: PathBuf,
    t0: Instant,
    sink: mc_engine::recorder::PreviewSink,
}

static SESSION: OnceLock<Mutex<Option<Session>>> = OnceLock::new();

fn session() -> &'static Mutex<Option<Session>> {
    SESSION.get_or_init(|| Mutex::new(None))
}

#[derive(Serialize)]
pub struct RecStatus {
    pub recording: bool,
    pub dir: String,
    pub elapsed: f64,
}

pub fn record_start(
    edit: String,
    monitor: Option<i32>,
    hw: Option<bool>,
) -> Result<String, String> {
    // None means no explicit choice (the hotkey path): use the saved
    // preference, but only when this machine can encode in hardware.
    let hw = Some(hw.unwrap_or_else(|| settings().hw_encode && nvenc_available()));
    mc_engine::mc_info!("record", "start: monitor={:?} hw={:?}", monitor, hw);
    if session().lock().unwrap().is_some() {
        return Err("已经在录制".into());
    }
    let ff = find_ffmpeg().ok_or("找不到 ffmpeg.exe")?;

    // the preview engine owns the duplication - release it first
    *last_start().lock().unwrap() = (edit.clone(), monitor, hw);
    preview_stop();
    mc_engine::hud::start();

    let mon = monitor_rect(monitor);
    if mon.w <= 0 || mon.h <= 0 {
        return Err("无法获取主显示器尺寸".into());
    }

    let mut s = Settings::default();
    parse_edit(&edit).cam.apply(&mut s);

    // GPU encoding keeps the recording near idle; software x264 costs about a
    // core and a half at 1440p30 with two streams running.
    let (vfmt, vq) = if hw.unwrap_or(false) {
        (mc_engine::ffmpeg::VideoFormat::Mp4Nvenc, 20)
    } else {
        (mc_engine::ffmpeg::VideoFormat::Mp4H264, 18)
    };

    let sink = mc_engine::recorder::new_sink();
    let cfg = mc_engine::RecorderConfig {
        mon,
        out_root: captures_root(),
        settings: s,
        record_master: true,
        format: vfmt,
        quality: vq,
        camera_format: vfmt,
        camera_quality: vq + 4,
        preview: Some(sink.clone()),
    };

    let rec = mc_engine::Recorder::start(cfg, ff)?;
    let root = rec.out_dir.clone();
    *session().lock().unwrap() = Some(Session {
        rec,
        root: root.clone(),
        t0: Instant::now(),
        sink,
    });
    Ok(root.display().to_string())
}

pub fn record_status() -> RecStatus {
    let g = session().lock().unwrap();
    match g.as_ref() {
        Some(s) => RecStatus {
            recording: true,
            dir: s.root.display().to_string(),
            elapsed: s.t0.elapsed().as_secs_f64(),
        },
        None => RecStatus {
            recording: false,
            dir: String::new(),
            elapsed: 0.0,
        },
    }
}

/// True while a recording is running (used by the window-close guard).
pub fn recording_active() -> bool {
    session().lock().unwrap().is_some()
}

pub fn record_stop() -> Result<String, String> {
    mc_engine::mc_info!("record", "stop requested");
    // take the session out before joining, so status polling never blocks on it
    let sess = session().lock().unwrap().take();
    let s = sess.ok_or_else(|| "没有在录制".to_string())?;
    let dir = s.root.clone();
    let sum = s.rec.stop()?;
    Ok(format!(
        "{}  ({} 帧 / {:.1}s)",
        dir.display(),
        sum.frames,
        sum.duration
    ))
}

// ============================================================
//  Proxy render (low-res cut used for smooth playback)
// ============================================================

pub fn render_proxy(dir: String, edit: String, height: u32) -> Result<String, String> {
    let clip = load_clip(std::path::Path::new(&dir))?;
    let ff = find_ffmpeg().ok_or("找不到 ffmpeg.exe")?;
    let (mut s, e) = build_settings(&dir, &edit)?;

    let h = (height.clamp(180, 1080)) & !1;
    let aspect = mc_engine::settings::aspect_value(s.aspect_idx);
    s.out_width = ((h as f32 * aspect).round() as i32).max(16) & !1;

    let out = PathBuf::from(&dir).join("proxy.mp4");
    let _sum = mc_engine::render_clip(
        &clip,
        &ff,
        &out,
        &s,
        &e,
        mc_engine::ffmpeg::VideoFormat::Mp4H264,
        30,
        |_, _| {},
    )?;
    Ok(out.display().to_string())
}

/// Absolute path of a clip's media file, for <video> playback.
pub fn media_path(dir: String, which: String) -> Result<String, String> {
    let base = PathBuf::from(&dir);
    let name = match which.as_str() {
        "master" => "master.mp4",
        "proxy" => "proxy.mp4",
        "camera" => "camera.mp4",
        _ => return Err(format!("未知媒体: {which}")),
    };
    let p = base.join(name);
    if !p.is_file() {
        return Err(format!("{} 不存在", p.display()));
    }
    Ok(p.display().to_string())
}

pub fn proxy_exists(dir: String) -> bool {
    PathBuf::from(&dir).join("proxy.mp4").is_file()
}


// ============================================================
//  Live preview (idle). While recording, the recorder's own sink is used
//  instead - DXGI allows only one duplication per output.
// ============================================================

struct PreviewEng {
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
    sink: mc_engine::recorder::PreviewSink,
    params: Arc<Mutex<Settings>>,
}

static PREVIEW: OnceLock<Mutex<Option<PreviewEng>>> = OnceLock::new();

fn preview() -> &'static Mutex<Option<PreviewEng>> {
    PREVIEW.get_or_init(|| Mutex::new(None))
}

fn cursor_pos() -> mc_engine::Vec2 {
    unsafe {
        let mut p = windows::Win32::Foundation::POINT::default();
        if windows::Win32::UI::WindowsAndMessaging::GetCursorPos(&mut p).is_ok() {
            mc_engine::Vec2::new(p.x as f32, p.y as f32)
        } else {
            mc_engine::Vec2::default()
        }
    }
}

#[derive(Serialize, Clone)]
pub struct MonitorDto {
    pub index: i32,
    pub x: i32,
    pub y: i32,
    pub w: i32,
    pub h: i32,
    pub primary: bool,
    pub label: String,
}

/// Adopts `rec_*` folders that have a recording but no `meta.json`, which is what
/// a crash or a forced close leaves behind. Without this they exist on disk and
/// are invisible in the library, so the take is effectively lost.
pub fn recover_orphan_clips() -> usize {
    let root = captures_root();
    let Ok(rd) = std::fs::read_dir(&root) else {
        return 0;
    };
    let mon = list_monitors()
        .into_iter()
        .find(|m| m.primary)
        .or_else(|| list_monitors().into_iter().next());
    let Some(mon) = mon else {
        return 0;
    };
    let mut recovered = 0;
    for e in rd.flatten() {
        let dir = e.path();
        if !dir.is_dir() {
            continue;
        }
        let name = dir.file_name().and_then(|s| s.to_str()).unwrap_or("");
        if !name.starts_with("rec_") || dir.join("meta.json").exists() {
            continue;
        }
        let master = dir.join("master.mp4");
        let track = dir.join("track.csv");
        if !master.exists() || !track.exists() {
            continue;
        }
        let duration = find_ffmpeg()
            .map(|ff| mc_engine::ffmpeg::media_duration(&ff, &master))
            .unwrap_or(0.0);
        let frames = std::fs::read_to_string(dir.join("frames.csv"))
            .map(|t| t.lines().count())
            .unwrap_or(0);
        let meta = format!(
            concat!(
                "{{\n",
                "  \"app\": \"MouseCam\",\n",
                "  \"recovered\": true,\n",
                "  \"complete\": false,\n",
                "  \"monitor\": {{\"x\": {}, \"y\": {}, \"w\": {}, \"h\": {}}},\n",
                "  \"fps\": 30,\n",
                "  \"outWidth\": 1080,\n",
                "  \"outHeight\": 608,\n",
                "  \"aspectIdx\": 0,\n",
                "  \"zoom\": 1.0,\n",
                "  \"duration\": {:.6},\n",
                "  \"frames\": {}\n",
                "}}\n"
            ),
            mon.x, mon.y, mon.w, mon.h, duration, frames.max(1)
        );
        if std::fs::write(dir.join("meta.json"), meta).is_ok() {
            recovered += 1;
            mc_engine::mc_warn!(
                "captures",
                "adopted an interrupted recording: {} ({:.1}s)",
                name,
                duration
            );
        }
    }
    recovered
}

pub fn list_monitors() -> Vec<MonitorDto> {
    mc_engine::capture::monitors()
        .into_iter()
        .enumerate()
        .map(|(i, m)| MonitorDto {
            index: i as i32,
            x: m.x,
            y: m.y,
            w: m.w,
            h: m.h,
            primary: m.primary,
            label: format!(
                "\u{5c4f}\u{5e55} {} \u{b7} {}\u{d7}{}{}",
                i + 1,
                m.w,
                m.h,
                if m.primary { " \u{b7} \u{4e3b}" } else { "" }
            ),
        })
        .collect()
}

/// Resolves the requested display, clamped to what actually exists.
fn monitor_rect(which: Option<i32>) -> mc_engine::IRect {
    let list = mc_engine::capture::monitors();
    let i = which.unwrap_or(0).max(0) as usize;
    match list.get(i).or_else(|| list.first()).copied() {
        Some(m) => mc_engine::IRect::new(m.x, m.y, m.w, m.h),
        None => mc_engine::capture::primary_monitor_rect(),
    }
}

pub fn preview_start(edit: String, monitor: Option<i32>) -> Result<(), String> {
    *last_start().lock().unwrap() = (edit.clone(), monitor, None);
    preview_stop();
    mc_engine::hud::start();

    let mon = monitor_rect(monitor);
    if mon.w <= 0 || mon.h <= 0 {
        return Err("无法获取显示器尺寸".into());
    }

    let mut s = Settings::default();
    parse_edit(&edit).cam.apply(&mut s);

    let sink = mc_engine::recorder::new_sink();
    let params = Arc::new(Mutex::new(s));
    let stop = Arc::new(AtomicBool::new(false));

    let sink2 = sink.clone();
    let params2 = params.clone();
    let stop2 = stop.clone();

    let handle = std::thread::Builder::new()
        .name("mc-preview".into())
        .spawn(move || {
            let mut cap = match mc_engine::capture::Capture::open(mon) {
                Ok(c) => c,
                Err(_) => return,
            };
            let mut cam = mc_engine::Camera::new();
            cam.set_screen(mon);

            let mut buf = vec![0u32; (mon.w * mon.h) as usize];
            let mut out: Vec<u32> = Vec::new();
            let mut rs = mc_engine::resample::Resampler::new();
            let mut sprites = mc_engine::cursor::SpriteCache::new();

            let step = 1.0 / 250.0;
            let mut next = Instant::now() + Duration::from_secs_f64(step);
            let mut t_prev = 0.0f64;
            let t0 = Instant::now();
            let pos0 = cursor_pos();
            cam.reset(pos0);
            let mut tick: u64 = 0;
            // The preview path used to be completely silent, so a frozen or black
            // preview left no trace at all. These two counters fix that.
            let mut published: u64 = 0;
            let mut grab_fails: u64 = 0;

            while !stop2.load(Ordering::Relaxed) {
                let t = t0.elapsed().as_secs_f64();
                let mut dt = t - t_prev;
                if dt < 1.0 / 1000.0 {
                    dt = 1.0 / 1000.0;
                }
                if dt > 1.0 / 25.0 {
                    dt = 1.0 / 25.0;
                }
                t_prev = t;
                let pos = cursor_pos();
                let s = params2.lock().unwrap().clone();
                cam.tick(&s, pos, dt);
                tick += 1;

                // capture roughly 15 times a second
                if tick % 16 == 0 && cap.grab(&mut buf) {
                    let r = cam.source_rect();
                    let mut lx = r.x - mon.x;
                    let mut ly = r.y - mon.y;
                    let mut rw = r.w;
                    let mut rh = r.h;
                    if lx < 0 { lx = 0; }
                    if ly < 0 { ly = 0; }
                    if lx + rw > mon.w { rw = mon.w - lx; }
                    if ly + rh > mon.h { rh = mon.h - ly; }
                    if rw >= 4 && rh >= 4 {
                        mc_engine::hud::set_frame(
                            Some(mc_engine::IRect::new(lx + mon.x, ly + mon.y, rw, rh)),
                            Some(mon),
                            &format!("{}×{}", rw, rh),
                        );
                        let pw = 1080i32.min(rw) & !1;
                        let ph = ((pw as f32 * rh as f32 / rw as f32).round() as i32).max(2) & !1;
                        out.resize((pw * ph) as usize, 0);
                        published += 1;
                        if published % 90 == 0 {
                            mc_engine::mc_debug!("preview", "{} frames published, crop {}x{}", published, rw, rh);
                        }
                        rs.prep(lx as f32, ly as f32, rw as f32, rh as f32, pw, ph);
                        rs.run(&buf, mon.w, mon.h, &mut out, pw);

                        if let Some(spr) = sprites.get() {
                            let sc = pw as f32 / rw as f32;
                            mc_engine::cursor::draw(
                                &mut out, pw, ph,
                                (pos.x - r.x as f32) * sc,
                                (pos.y - r.y as f32) * sc,
                                sc, spr,
                            );
                        }
                        if let Ok(mut g) = sink2.lock() {
                            *g = Some(mc_engine::recorder::PreviewShot {
                                w: pw as u32,
                                h: ph as u32,
                                px: out.clone(),
                            });
                            // A frame counter alone cannot tell "producing" from "producing black".
                            // Sample the output so a black preview says so in the log.
                            if published % 45 == 0 {
                                let step = (out.len() / 512).max(4);
                                let sum: u64 = out.iter().step_by(step).map(|&v| (v >> 16 & 0xFF) as u64
                                    + (v >> 8 & 0xFF) as u64 + (v & 0xFF) as u64).sum();
                                let n = (out.len() / step).max(1) as u64;
                                let luma = sum / (n * 3);
                                if luma < 6 {
                                    mc_engine::mc_warn!("preview", "published frame {} is BLACK (luma {})", published, luma);
                                } else {
                                    mc_engine::mc_debug!("preview", "frame {} luma {} crop {}x{}", published, luma, rw, rh);
                                }
                            }
                        }
                    }
                } else if tick % 16 == 0 {
                    grab_fails += 1;
                    if grab_fails % 20 == 1 {
                        mc_engine::mc_warn!("preview", "capture grab failed ({} times)", grab_fails);
                    }
                }
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
        .map_err(|e| format!("启动预览线程失败: {e}"))?;

    *preview().lock().unwrap() = Some(PreviewEng {
        stop,
        handle: Some(handle),
        sink,
        params,
    });
    Ok(())
}

pub fn preview_stop() {
    mc_engine::hud::set_rect(None, "");
    let eng = preview().lock().unwrap().take();
    if let Some(mut e) = eng {
        e.stop.store(true, Ordering::Relaxed);
        if let Some(h) = e.handle.take() {
            let _ = h.join();
        }
    }
}

pub fn preview_set_params(edit: String) {
    let g = preview().lock().unwrap();
    if let Some(e) = g.as_ref() {
        let mut s = Settings::default();
        parse_edit(&edit).cam.apply(&mut s);
        *e.params.lock().unwrap() = s;
    }
}

/// Latest follow-cam frame as a JPEG data URL (works while recording too).
pub fn preview_frame() -> Result<String, String> {
    let shot = preview_shot()?;
    encode_jpeg(&shot.px, shot.w, shot.h, 82)
}

pub fn hud_set(enabled: bool) {
    mc_engine::hud::set_enabled(enabled);
    if enabled {
        mc_engine::hud::start();
    } else {
        mc_engine::hud::set_rect(None, "");
    }
}

pub fn hud_get() -> bool {
    mc_engine::hud::enabled()
}

pub fn hud_set_config(thickness: i32, label: bool, brackets: bool) {
    mc_engine::hud::set_config(mc_engine::hud::HudConfig {
        thickness: thickness.clamp(1, 8),
        show_label: label,
        brackets,
    });
}

pub fn hud_get_config() -> (i32, bool, bool) {
    let c = mc_engine::hud::config();
    (c.thickness, c.show_label, c.brackets)
}

pub fn preview_active() -> bool {
    if session().lock().unwrap().is_some() {
        return true;
    }
    preview().lock().unwrap().is_some()
}

/// Decode size for one still: never above the source, never so small that the
/// requested output would have to be upscaled.
fn still_decode_size(
    mon: &mc_engine::IRect,
    kind: &str,
    rect: &mc_engine::IRect,
    max_w: u32,
) -> (i32, i32) {
    let even = |v: f32| ((v.round() as i32).max(2)) & !1;
    let mut w = if kind == "crop" {
        let frac = (rect.w.min(mon.w).max(1) as f32) / mon.w as f32;
        (max_w as f32 / frac).min(mon.w as f32)
    } else {
        max_w as f32
    };
    w = w.clamp(320.0, mon.w as f32);
    let d_w = even(w).min(mon.w & !1);
    let d_h = even(d_w as f32 * mon.h as f32 / mon.w as f32).min(mon.h & !1);
    (d_w, d_h)
}


// ============================================================
//  Global hotkeys: Ctrl+Alt+R or F9 toggles recording, so a take can be
//  started without bringing the window forward.
// ============================================================

fn last_start() -> &'static Mutex<(String, Option<i32>, Option<bool>)> {
    static LAST: OnceLock<Mutex<(String, Option<i32>, Option<bool>)>> = OnceLock::new();
    LAST.get_or_init(|| Mutex::new((String::new(), None, None)))
}

static HOTKEYS: OnceLock<Mutex<Option<HotkeyThread>>> = OnceLock::new();
static HOTKEY_FLAGS: OnceLock<Mutex<(bool, bool)>> = OnceLock::new();

struct HotkeyThread {
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

fn hotkeys() -> &'static Mutex<Option<HotkeyThread>> {
    HOTKEYS.get_or_init(|| Mutex::new(None))
}

fn hotkey_flags() -> &'static Mutex<(bool, bool)> {
    HOTKEY_FLAGS.get_or_init(|| Mutex::new((false, false)))
}

/// (Ctrl+Alt+R registered, F9 registered)
pub fn hotkey_status() -> (bool, bool) {
    *hotkey_flags().lock().unwrap()
}

fn toggle_recording() {
    let recording = session().lock().unwrap().is_some();
    if recording {
        let _ = record_stop();
    } else {
        let (edit, mon, hw) = last_start().lock().unwrap().clone();
        let _ = record_start(edit, mon, hw);
    }
}

pub fn hotkeys_start() {
    if hotkeys().lock().unwrap().is_some() {
        return;
    }
    let stop = Arc::new(AtomicBool::new(false));
    let stop2 = stop.clone();

    let handle = std::thread::Builder::new()
        .name("mc-hotkeys".into())
        .spawn(move || unsafe {
            use windows::Win32::UI::Input::KeyboardAndMouse::{
                RegisterHotKey, UnregisterHotKey, MOD_ALT, MOD_CONTROL, MOD_NOREPEAT,
            };
            use windows::Win32::UI::WindowsAndMessaging::{PeekMessageW, MSG, PM_REMOVE, WM_HOTKEY};

            const ID_COMBO: i32 = 0xA1;
            const ID_F9: i32 = 0xA2;

            let a = RegisterHotKey(
                None,
                ID_COMBO,
                MOD_CONTROL | MOD_ALT | MOD_NOREPEAT,
                0x52, // 'R'
            )
            .is_ok();
            let b = RegisterHotKey(None, ID_F9, MOD_NOREPEAT, 0x78).is_ok();
            *hotkey_flags().lock().unwrap() = (a, b);

            while !stop2.load(Ordering::Relaxed) {
                let mut msg = MSG::default();
                while PeekMessageW(&mut msg, None, 0, 0, PM_REMOVE).as_bool() {
                    if msg.message == WM_HOTKEY {
                        let id = msg.wParam.0 as i32;
                        if id == ID_COMBO || id == ID_F9 {
                            toggle_recording();
                        }
                    }
                }
                std::thread::sleep(Duration::from_millis(12));
            }

            let _ = UnregisterHotKey(None, ID_COMBO);
            let _ = UnregisterHotKey(None, ID_F9);
        })
        .ok();

    *hotkeys().lock().unwrap() = Some(HotkeyThread { stop, handle });
}

pub fn hotkeys_stop() {
    let t = hotkeys().lock().unwrap().take();
    if let Some(mut t) = t {
        t.stop.store(true, Ordering::Relaxed);
        if let Some(h) = t.handle.take() {
            let _ = h.join();
        }
    }
}

/// Whether the GPU encoder can actually be used here.
pub fn nvenc_available() -> bool {
    match find_ffmpeg() {
        Some(ff) => mc_engine::ffmpeg::nvenc_available(&ff),
        None => false,
    }
}

/// (effective output dir, configured dir or "" for the default, hw, hud)
pub fn app_settings() -> (String, String, bool, bool, bool) {
    let st = settings();
    let effective = captures_root().display().to_string();
    (
        effective,
        st.captures_dir.unwrap_or_default(),
        st.hw_encode,
        st.hud_default,
        st.verbose,
    )
}

pub fn set_app_settings(
    captures_dir: String,
    hw: bool,
    hud: bool,
    verbose: bool,
) -> Result<(), String> {
    // Saves used to succeed with an unusable folder, and the failure only showed
    // up later as "创建目录失败" when recording started. Refuse it here instead.
    let trimmed = captures_dir.trim();
    if !trimmed.is_empty() {
        let p = PathBuf::from(trimmed);
        std::fs::create_dir_all(&p).map_err(|e| format!("无法创建该文件夹: {e}"))?;
        if !writable(&p) {
            return Err(format!("该文件夹不可写: {}", p.display()));
        }
    }
    set_settings(captures_dir, hw, hud, verbose)
        .map_err(|e| e)
        .inspect(|_| mc_engine::log::set_verbose(verbose))
}
