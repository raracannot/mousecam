//! Headless re-render driver (parity harness for the C++ build).
//!
//!   mc-render --clip <rec_dir> [--edit <file.mcl>] [--out <file.mp4>]
//!             [--zoom 1.2] [--expand 1.6] [--smooth 70] [--follow 1.8]
//!             [--aspect 2] [--width 1080] [--fps 30]

use mc_engine::capture::{primary_monitor_rect, Capture};
use mc_engine::recorder::{Recorder, RecorderConfig};
use mc_engine::clip::{find_ffmpeg, load_clip, settings_from_meta};
use mc_engine::edit::{parse_edit, RenderOpts};
use mc_engine::ffmpeg::VideoFormat;
use mc_engine::render::render_clip;
use std::path::PathBuf;
use std::time::Instant;

fn capture_bench(args: &[String]) {
    let frames: usize = args.get(1).and_then(|v| v.parse().ok()).unwrap_or(60);
    let mon = primary_monitor_rect();
    println!("monitor {}x{} at {},{}", mon.w, mon.h, mon.x, mon.y);

    let mut cap = match Capture::open(mon) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("抓屏初始化失败: {e}");
            std::process::exit(1);
        }
    };
    println!("path    {:?}", cap.path);

    let mut buf = vec![0u32; (mon.w * mon.h) as usize];
    for i in 0..8 {
        let ok = cap.grab(&mut buf);
        std::thread::sleep(std::time::Duration::from_millis(20));
    }

    let mut times: Vec<f64> = Vec::new();
    let mut ok_count = 0;
    for _ in 0..frames {
        let t = std::time::Instant::now();
        let ok = cap.grab(&mut buf);
        let ms = t.elapsed().as_secs_f64() * 1000.0;
        if ok {
            times.push(ms);
            ok_count += 1;
        }
        std::thread::sleep(std::time::Duration::from_millis(30));
    }

    let n = times.len().max(1);
    let avg = times.iter().sum::<f64>() / n as f64;
    let max = times.iter().cloned().fold(0.0f64, f64::max);
    let min = times.iter().cloned().fold(f64::MAX, f64::min);
    // cheap content check: sampled pixel sum
    let sum: u64 = buf.iter().step_by(99991).map(|&p| p as u64 & 0xFF).sum();
    println!(
        "grabs   {}/{} ok   avg {:.2} ms   min {:.2} ms   max {:.2} ms",
        ok_count, frames, avg, min, max
    );
    println!("content checksum {sum}  (0 would mean a black frame)");

    // dump one frame so the orientation / channel order can be eyeballed
    let bytes: &[u8] = unsafe {
        std::slice::from_raw_parts(buf.as_ptr() as *const u8, buf.len() * 4)
    };
    let dump = std::path::Path::new("capture_frame.raw");
    if std::fs::write(dump, bytes).is_ok() {
        println!("dumped  {}", dump.display());
    }
}

fn enable_dpi_awareness() {
    use windows::Win32::UI::HiDpi::{
        SetProcessDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
    };
    unsafe {
        let _ = SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    }
}

fn record_test(args: &[String]) {
    let secs: f64 = args.get(1).and_then(|v| v.parse().ok()).unwrap_or(6.0);
    let mon = primary_monitor_rect();
    println!("monitor {}x{} at {},{}", mon.w, mon.h, mon.x, mon.y);

    let ffmpeg = match find_ffmpeg() {
        Some(f) => f,
        None => {
            eprintln!("找不到 ffmpeg.exe");
            std::process::exit(1);
        }
    };

    let mut cfg = RecorderConfig::default();
    cfg.mon = mon;
    cfg.out_root = std::path::PathBuf::from("captures");

    let rec = match Recorder::start(cfg, ffmpeg) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("开始录制失败: {e}");
            std::process::exit(1);
        }
    };
    println!("recording {:.1}s -> {}", secs, rec.out_dir.display());
    std::thread::sleep(std::time::Duration::from_secs_f64(secs));

    match rec.stop() {
        Ok(s) => println!(
            "done    frames={} duration={:.2}s dropped={} dir={}",
            s.frames,
            s.duration,
            s.dropped,
            s.out_dir.display()
        ),
        Err(e) => {
            eprintln!("录制失败: {e}");
            std::process::exit(1);
        }
    }
}

fn main() {
    enable_dpi_awareness();
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.first().map(|s| s.as_str()) == Some("--record") {
        record_test(&args);
        return;
    }
    if args.first().map(|s| s.as_str()) == Some("--capture-bench") {
        capture_bench(&args);
        return;
    }
    if args.is_empty() {
        eprintln!("用法: mc-render --clip <录制目录> [--edit <file.mcl>] [--out <file.mp4>] ...");
        std::process::exit(2);
    }

    let mut clip_dir: Option<PathBuf> = None;
    let mut edit_file: Option<PathBuf> = None;
    let mut out_file: Option<PathBuf> = None;
    let mut cli = RenderOpts::default();

    let mut i = 0;
    while i < args.len() {
        let key = args[i].as_str();
        let val = args.get(i + 1).cloned();
        match (key, val) {
            ("--clip", Some(v)) => clip_dir = Some(PathBuf::from(v)),
            ("--edit", Some(v)) => edit_file = Some(PathBuf::from(v)),
            ("--out", Some(v)) => out_file = Some(PathBuf::from(v)),
            ("--zoom", Some(v)) => cli.zoom = v.parse().unwrap_or(-1.0),
            ("--expand", Some(v)) => cli.expand = v.parse().unwrap_or(-1.0),
            ("--threshold", Some(v)) => cli.threshold = v.parse().unwrap_or(-1.0),
            ("--smooth", Some(v)) => cli.smooth = v.parse().unwrap_or(-1.0),
            ("--resp", Some(v)) => cli.resp = v.parse().unwrap_or(-1.0),
            ("--follow", Some(v)) => cli.follow = v.parse().unwrap_or(-1.0),
            ("--look", Some(v)) => cli.look = v.parse().unwrap_or(-1.0),
            ("--aspect", Some(v)) => cli.aspect = v.parse().unwrap_or(-1),
            ("--width", Some(v)) => cli.width = v.parse().unwrap_or(-1),
            ("--fps", Some(v)) => cli.fps = v.parse().unwrap_or(-1),
            _ => {
                i += 1;
                continue;
            }
        }
        i += 2;
    }

    let dir = match clip_dir {
        Some(d) => d,
        None => {
            eprintln!("缺少 --clip");
            std::process::exit(2);
        }
    };

    let clip = match load_clip(&dir) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("打开素材失败: {e}");
            std::process::exit(1);
        }
    };

    let mut settings = match settings_from_meta(&dir) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("读取参数失败: {e}");
            std::process::exit(1);
        }
    };

    // no --edit given: pick up a sibling edit.mcl
    let edit_path = edit_file.or_else(|| {
        let p = dir.join("edit.mcl");
        if p.is_file() {
            Some(p)
        } else {
            None
        }
    });
    let edit = match edit_path {
        Some(p) => match std::fs::read_to_string(&p) {
            Ok(t) => parse_edit(&t),
            Err(e) => {
                eprintln!("读取编辑清单失败: {e}");
                std::process::exit(1);
            }
        },
        None => Default::default(),
    };

    edit.cam.apply(&mut settings);
    cli.apply(&mut settings);

    let ffmpeg = match find_ffmpeg() {
        Some(f) => f,
        None => {
            eprintln!("找不到 ffmpeg.exe（可设置 MC_FFMPEG 环境变量）");
            std::process::exit(1);
        }
    };

    let out = out_file.unwrap_or_else(|| dir.join("camera_rust.mp4"));
    let out = if out.is_absolute() {
        out
    } else {
        dir.join(out)
    };

    println!("ffmpeg  {}", ffmpeg.display());
    println!("clip    {}", dir.display());
    println!("out     {}", out.display());

    let t0 = Instant::now();
    let mut last = -1i32;
    let res = render_clip(
        &clip,
        &ffmpeg,
        &out,
        &settings,
        &edit,
        VideoFormat::Mp4H264,
        18,
        |done, total| {
            if done - last >= 60 {
                last = done;
                let el = t0.elapsed().as_secs_f64();
                println!(
                    "  {done}/{total} frames  {el:.1}s  ({:.1}x realtime)",
                    (done as f64 / settings.fps as f64) / el.max(1e-6)
                );
            }
        },
    );

    match res {
        Ok(sum) => {
            println!(
                "done    {} frames  {:.2}s  rendered in {:.2}s ({:.1}x realtime)",
                sum.frames,
                sum.duration,
                sum.elapsed,
                sum.duration / sum.elapsed.max(1e-6)
            );
            println!("file    {}", sum.out_path.display());
        }
        Err(e) => {
            eprintln!("渲染失败: {e}");
            std::process::exit(1);
        }
    }
}
