//! ffmpeg as a child process: raw BGRA frames in on stdin, raw BGRA frames out
//! on stdout. `std::process` handles the pipes, so there is no hand-written
//! handle inheritance here.

use std::io::{Read, Write};
use std::os::windows::process::CommandExt;
use std::path::Path;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};

const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum VideoFormat {
    Mp4H264,
    Mp4Nvenc,
    MkvH265,
    WebmVp9,
    Gif,
    MovProres,
}

impl VideoFormat {
    pub fn label(&self) -> &'static str {
        match self {
            VideoFormat::Mp4H264 => "MP4 · H.264",
            VideoFormat::Mp4Nvenc => "MP4 · H.264 (NVENC)",
            VideoFormat::MkvH265 => "MKV · H.265",
            VideoFormat::WebmVp9 => "WebM · VP9",
            VideoFormat::Gif => "GIF",
            VideoFormat::MovProres => "MOV · ProRes",
        }
    }

    /// Stable identifier used by the UI and the CLI.
    pub fn id(&self) -> &'static str {
        match self {
            VideoFormat::Mp4H264 => "mp4_h264",
            VideoFormat::Mp4Nvenc => "mp4_h264_nvenc",
            VideoFormat::MkvH265 => "mkv_h265",
            VideoFormat::WebmVp9 => "webm_vp9",
            VideoFormat::Gif => "gif",
            VideoFormat::MovProres => "mov_prores",
        }
    }

    pub fn parse(s: &str) -> VideoFormat {
        match s {
            "mp4_h264_nvenc" => VideoFormat::Mp4Nvenc,
            "mkv_h265" => VideoFormat::MkvH265,
            "webm_vp9" => VideoFormat::WebmVp9,
            "gif" => VideoFormat::Gif,
            "mov_prores" => VideoFormat::MovProres,
            _ => VideoFormat::Mp4H264,
        }
    }

    pub fn extension(&self) -> &'static str {
        match self {
            VideoFormat::MkvH265 => "mkv",
            VideoFormat::WebmVp9 => "webm",
            VideoFormat::Gif => "gif",
            VideoFormat::MovProres => "mov",
            _ => "mp4",
        }
    }

    fn codec_args(&self, crf: i32) -> Vec<String> {
        let mut a: Vec<String> = Vec::new();
        match self {
            VideoFormat::Mp4H264 => a.extend(
                [
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", &crf.to_string(),
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                ]
                .iter()
                .map(|s| s.to_string()),
            ),
            VideoFormat::Mp4Nvenc => a.extend(
                [
                    "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr",
                    "-cq", &(crf + 4).to_string(), "-b:v", "0",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                ]
                .iter()
                .map(|s| s.to_string()),
            ),
            VideoFormat::MkvH265 => a.extend(
                [
                    "-c:v", "libx265", "-preset", "veryfast", "-crf", &(crf + 2).to_string(),
                    "-pix_fmt", "yuv420p", "-x265-params", "log-level=error",
                ]
                .iter()
                .map(|s| s.to_string()),
            ),
            VideoFormat::WebmVp9 => a.extend(
                [
                    "-c:v", "libvpx-vp9", "-crf", &crf.to_string(), "-b:v", "0",
                    "-deadline", "realtime", "-cpu-used", "5", "-pix_fmt", "yuv420p",
                ]
                .iter()
                .map(|s| s.to_string()),
            ),
            VideoFormat::Gif => a.extend(
                [
                    "-filter_complex",
                    "[0:v]split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];\
                     [b][p]paletteuse=dither=bayer:bayer_scale=3",
                    "-loop", "0",
                ]
                .iter()
                .map(|s| s.to_string()),
            ),
            VideoFormat::MovProres => a.extend(
                ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"]
                    .iter()
                    .map(|s| s.to_string()),
            ),
        }
        a.push("-an".into());
        a
    }
}

/// Runs a throwaway 1-frame encode to find out whether the GPU encoder really
/// works. Listing `-encoders` only proves the binary was built with it.
pub fn nvenc_available(ffmpeg: &Path) -> bool {
    let mut cmd = Command::new(ffmpeg);
    cmd.args([
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=320x240:r=10:d=0.2",
        "-c:v",
        "h264_nvenc",
        "-f",
        "null",
        "-",
    ]);
    match no_window(&mut cmd).output() {
        Ok(o) => o.status.success(),
        Err(_) => false,
    }
}

fn no_window(cmd: &mut Command) -> &mut Command {
    cmd.creation_flags(CREATE_NO_WINDOW)
}

/// Pipes raw BGRA frames into ffmpeg.
pub struct FrameWriter {
    child: Child,
    stdin: Option<ChildStdin>,
    /// ffmpeg's own complaints, kept so a failure can say why. Without this the
    /// only symptom is a pipe that closes and a file that is too small.
    stderr: std::sync::Arc<std::sync::Mutex<String>>,
    done: bool,
    pub w: i32,
    pub h: i32,
    pub path: String,
}

impl FrameWriter {
    pub fn open(
        ffmpeg: &Path,
        out: &Path,
        w: i32,
        h: i32,
        fps: i32,
        fmt: VideoFormat,
        crf: i32,
    ) -> Result<Self, String> {
        let mut cmd = Command::new(ffmpeg);
        cmd.args(["-hide_banner", "-loglevel", "error", "-y"])
            .args(["-f", "rawvideo", "-pix_fmt", "bgra"])
            .args(["-s", &format!("{}x{}", w, h)])
            .args(["-r", &fps.to_string()])
            .args(["-i", "-"]);
        for a in fmt.codec_args(crf) {
            cmd.arg(a);
        }
        cmd.arg(out);

        let mut child = no_window(&mut cmd)
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("启动 ffmpeg 失败: {e}"))?;

        let stdin = child.stdin.take().ok_or("ffmpeg stdin 不可用")?;
        // Drained on its own thread: a full stderr pipe would block ffmpeg, and
        // that looks exactly like a slow encode.
        let stderr = std::sync::Arc::new(std::sync::Mutex::new(String::new()));
        if let Some(mut pipe) = child.stderr.take() {
            let sink = stderr.clone();
            std::thread::spawn(move || {
                use std::io::Read;
                let mut chunk = [0u8; 4096];
                while let Ok(n) = pipe.read(&mut chunk) {
                    if n == 0 {
                        break;
                    }
                    if let Ok(mut s) = sink.lock() {
                        if s.len() > 60_000 {
                            s.clear();
                        }
                        s.push_str(&String::from_utf8_lossy(&chunk[..n]));
                    }
                }
            });
        }
        Ok(Self {
            child,
            stdin: Some(stdin),
            stderr,
            done: false,
            w,
            h,
            path: out.display().to_string(),
        })
    }

    pub fn write_frame(&mut self, px: &[u32]) -> std::io::Result<()> {
        let bytes: &[u8] = unsafe {
            std::slice::from_raw_parts(px.as_ptr() as *const u8, px.len() * std::mem::size_of::<u32>())
        };
        if let Some(si) = self.stdin.as_mut() {
            si.write_all(bytes)?;
        }
        Ok(())
    }

    /// Closes stdin and waits for ffmpeg to finish.
    /// Stops the encoder right now. Used when a render is abandoned, where
    /// closing stdin politely would leave ffmpeg holding the output file open
    /// for long enough that deleting it fails and a half-written file survives.
    pub fn abort(mut self) {
        self.stdin.take();
        let _ = self.child.kill();
        let _ = self.child.wait();
        self.done = true;
        std::thread::sleep(std::time::Duration::from_millis(30));
    }

    /// Last few hundred characters ffmpeg printed, for error messages.
    fn tail(&self) -> String {
        let s = match self.stderr.lock() {
            Ok(g) => g.clone(),
            Err(_) => return String::new(),
        };
        let t = s.trim();
        // chars, not bytes: slicing a UTF-8 string at a byte offset panics
        let tail: String = t.chars().rev().take(700).collect::<Vec<char>>().into_iter().rev().collect();
        tail
    }

    pub fn finish(mut self) -> (i32, String) {
        drop(self.stdin.take());
        let code = match self.child.wait() {
            Ok(st) => st.code().unwrap_or(-1),
            Err(_) => -1,
        };
        self.done = true;
        (code, self.tail())
    }
}

impl Drop for FrameWriter {
    /// A writer dropped on an early return must not leave ffmpeg running with
    /// the output file open - that is how a half written take survives.
    fn drop(&mut self) {
        if self.done {
            return;
        }
        drop(self.stdin.take());
        let _ = self.child.kill();
        let _ = self.child.wait();
        self.done = true;
    }
}

/// Pipes raw BGRA frames out of ffmpeg.
pub struct FrameReader {
    child: Child,
    stdout: ChildStdout,
    pub w: i32,
    pub h: i32,
}

impl FrameReader {
    /// `seek` positions the decoder before `input` (input seeking, frame accurate).
    pub fn open(ffmpeg: &Path, input: &Path, seek: Option<f64>, w: i32, h: i32) -> Result<Self, String> {
        Self::open_scaled(ffmpeg, input, seek, w, h, None)
    }

    /// Same, but asks ffmpeg to scale to `scale` first. Decoding 2560x1440 and
    /// piping 14.7 MB per frame dominates a single-frame read, so callers that
    /// only need a small image should decode small.
    pub fn open_scaled(
        ffmpeg: &Path,
        input: &Path,
        seek: Option<f64>,
        w: i32,
        h: i32,
        scale: Option<(i32, i32)>,
    ) -> Result<Self, String> {
        let mut cmd = Command::new(ffmpeg);
        cmd.args(["-hide_banner", "-loglevel", "error"]);
        if let Some(t) = seek {
            // land strictly before the frame boundary; accurate seek keeps
            // frames with pts >= ss
            cmd.args(["-ss", &format!("{:.6}", (t - 0.001).max(0.0))]);
        }
        cmd.args(["-i"]).arg(input);
        if let Some((sw, sh)) = scale {
            cmd.args(["-vf", &format!("scale={}:{}", sw, sh)]);
        }
        cmd.args(["-f", "rawvideo", "-pix_fmt", "bgra"]).arg("-");

        let mut child = no_window(&mut cmd)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("启动 ffmpeg 解码失败: {e}"))?;

        let stdout = child.stdout.take().ok_or("ffmpeg stdout 不可用")?;
        Ok(Self { child, stdout, w, h })
    }

    /// Returns false at end of stream.
    pub fn read_frame(&mut self, dst: &mut [u32]) -> bool {
        let bytes: &mut [u8] = unsafe {
            std::slice::from_raw_parts_mut(
                dst.as_mut_ptr() as *mut u8,
                dst.len() * std::mem::size_of::<u32>(),
            )
        };
        self.stdout.read_exact(bytes).is_ok()
    }
}

impl Drop for FrameReader {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// One stretch of the soundtrack: source seconds `[a, b)` play at `speed`.
#[derive(Clone, Copy, Debug)]
pub struct AudioPiece {
    pub a: f64,
    pub b: f64,
    pub speed: f64,
}

/// Reads `Duration: HH:MM:SS.ss` out of ffmpeg's banner.
/// Muxes WAV tracks into an already-encoded video, replacing it in place.
///
/// `at` is where the audio should start, so a trimmed render keeps the sound that
/// belongs to the frames it kept rather than the sound of the whole take. `dur`
/// caps the result: the picture is the authority on length, and the audio is
/// padded to reach it instead of cutting the video short.
///
/// `pieces` is the edit's source timeline: consecutive `[a, b)` spans with a
/// playback `speed`, already trimmed and speed-adjusted. When it is `None` the
/// whole track from `at` is used unchanged, which is the untrimmed case.
pub fn mux_audio(
    ffmpeg: &Path,
    video: &Path,
    tracks: &[std::path::PathBuf],
    at: f64,
    dur: Option<f64>,
    pieces: Option<&[AudioPiece]>,
) -> Result<(), String> {
    if tracks.is_empty() || !video.exists() {
        return Ok(());
    }
    let ext = video
        .extension()
        .map(|e| e.to_string_lossy().to_string())
        .unwrap_or_else(|| "mp4".into());
    let tmp = video.with_file_name(format!(
        "{}.mux.{ext}",
        video.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_default()
    ));
    let mut cmd = Command::new(ffmpeg);
    cmd.arg("-y").arg("-hide_banner").arg("-loglevel").arg("error");
    cmd.arg("-i").arg(video);
    // With an edit timeline every track is read from the top and cut by the
    // filter graph, because a source offset per track cannot express several
    // disjoint kept ranges.
    let per_piece = pieces.is_some();
    for t in tracks {
        if at > 0.0005 && !per_piece {
            cmd.arg("-ss").arg(format!("{at:.3}"));
        }
        cmd.arg("-i").arg(t);
    }
    cmd.arg("-map").arg("0:v:0");
    let graph_has_apad = pieces.filter(|l| !l.is_empty()).is_none();
    if let Some(list) = pieces.filter(|l| !l.is_empty()) {
        cmd.arg("-filter_complex").arg(audio_graph(tracks.len(), list));
        cmd.arg("-map").arg("[out]");
    } else if tracks.len() == 1 {
        cmd.arg("-map").arg("1:a:0").arg("-af").arg("apad");
    } else {
        let graph = format!(
            "[1:a][2:a]amix=inputs={}:duration=longest:normalize=0[mix];[mix]apad[a]",
            tracks.len()
        );
        cmd.arg("-filter_complex").arg(graph);
        cmd.arg("-map").arg("[a]");
    }
    cmd.arg("-c:v").arg("copy");
    cmd.arg("-c:a").arg("aac").arg("-b:a").arg("160k").arg("-ar").arg("48000");
    if let Some(d) = dur {
        if d > 0.0 {
            cmd.arg("-t").arg(format!("{d:.3}"));
        }
    }
    // The built-in paths keep -shortest: their audio can be longer than the
    // picture and must not stretch the file. With an edit graph the picture and
    // the soundtrack share one timeline and -t already fixes the length.
    if graph_has_apad {
        cmd.arg("-shortest");
    }
    if ext == "mp4" || ext == "mov" {
        cmd.arg("-movflags").arg("+faststart");
    }
    cmd.arg(&tmp);

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000);
    }
    let out = cmd
        .output()
        .map_err(|e| format!("调用 ffmpeg 封装音频失败: {e}"))?;
    if !out.status.success() {
        let _ = std::fs::remove_file(&tmp);
        return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());
    }
    if std::fs::remove_file(video).is_err() {
        let _ = std::fs::remove_file(&tmp);
        return Err("替换成片失败：无法删除原文件".into());
    }
    std::fs::rename(&tmp, video).map_err(|e| format!("替换成片失败: {e}"))
}

/// `atempo` only accepts one factor per filter, so a 4× stretch needs two
/// stages of 2×. Anything outside [0.5, 2.0] is split until it fits.
fn atempo_chain(mut speed: f64) -> Vec<f64> {
    let mut out = Vec::new();
    while speed > 2.0 {
        out.push(2.0);
        speed /= 2.0;
    }
    while speed < 0.5 {
        out.push(0.5);
        speed /= 0.5;
    }
    out.push(speed);
    out
}

/// The soundtrack for an edited timeline: every piece is cut out of its source
/// track, played at its speed and laid back-to-back, so picture and sound stay
/// in sync through speed changes and trims.
///
/// One graph serves every track: the pieces are mixed per track first, then
/// concatenated in timeline order.
fn audio_graph(tracks: usize, pieces: &[AudioPiece]) -> String {
    let mut g = String::new();
    for (ti, _) in (0..tracks).enumerate() {
        let src = ti + 1; // input 0 is the video
        let mut labels = Vec::with_capacity(pieces.len());
        for (pi, p) in pieces.iter().enumerate() {
            let label = format!("a{ti}_{pi}");
            let mut chain = format!(
                "[{src}:a]atrim=start={a:.4}:end={b:.4},asetpts=PTS-STARTPTS",
                a = p.a,
                b = p.b
            );
            for factor in atempo_chain(p.speed) {
                chain.push_str(&format!(",atempo={factor:.6}"));
            }
            chain.push_str(&format!(",aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[{label}]"));
            g.push_str(&chain);
            g.push(';');
            labels.push(label);
        }
        if labels.len() == 1 {
            g.push_str(&format!("[{}]anull[a{}];", labels[0], ti));
        } else {
            let inputs: String = labels.iter().map(|l| format!("[{l}]")).collect();
            g.push_str(&format!(
                "{inputs}concat=n={n}:v=0:a=1[a{ti}];",
                n = labels.len(),
                ti = ti
            ));
        }
    }
    let all: String = (0..tracks).map(|i| format!("[a{i}]")).collect();
    if tracks == 1 {
        g.push_str(&format!("{all}anull[out]"));
    } else {
        g.push_str(&format!(
            "{all}amix=inputs={tracks}:duration=longest:normalize=0[out]"
        ));
    }
    g
}

pub fn media_duration(ffmpeg: &Path, file: &Path) -> f64 {
    let mut cmd = Command::new(ffmpeg);
    cmd.args(["-hide_banner", "-i"]).arg(file);
    let out = match no_window(&mut cmd).output() {
        Ok(o) => o,
        Err(_) => return 0.0,
    };
    let text = String::from_utf8_lossy(&out.stderr);
    let pos = match text.find("Duration:") {
        Some(p) => p,
        None => return 0.0,
    };
    let tail = &text[pos + 9..];
    let token = tail.split(',').next().unwrap_or("").trim();
    let mut it = token.split(':');
    let h: f64 = it.next().and_then(|v| v.trim().parse().ok()).unwrap_or(0.0);
    let m: f64 = it.next().and_then(|v| v.trim().parse().ok()).unwrap_or(0.0);
    let s: f64 = it.next().and_then(|v| v.trim().parse().ok()).unwrap_or(0.0);
    h * 3600.0 + m * 60.0 + s
}
