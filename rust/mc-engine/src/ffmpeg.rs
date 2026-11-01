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
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("启动 ffmpeg 失败: {e}"))?;

        let stdin = child.stdin.take().ok_or("ffmpeg stdin 不可用")?;
        Ok(Self {
            child,
            stdin: Some(stdin),
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
    pub fn finish(mut self) -> i32 {
        drop(self.stdin.take());
        match self.child.wait() {
            Ok(st) => st.code().unwrap_or(-1),
            Err(_) => -1,
        }
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

/// Reads `Duration: HH:MM:SS.ss` out of ffmpeg's banner.
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
