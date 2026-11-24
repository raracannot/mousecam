//! Records a short synthetic take and checks the files describe each other.
//!
//! `Capture::open_synthetic` and `record_start(synthetic: true)` exist so the
//! whole chain can be exercised without touching the desktop, but nothing used
//! them. This is the end-to-end case: it runs the recorder, then reads the take
//! back the way the editor does and asserts the parts agree.

use std::path::PathBuf;
use std::time::Duration;

use mc_engine::IRect;
use mc_engine::clip::find_ffmpeg;
use mc_engine::recorder::{Recorder, RecorderConfig};
use mc_engine::settings::Settings;

fn temp_root() -> PathBuf {
    // CARGO_TARGET_TMPDIR is a scratch area cargo guarantees for integration
    // tests; the system temp dir is not always writable (sandboxes, policy).
    let p = PathBuf::from(env!("CARGO_TARGET_TMPDIR")).join(format!(
        "mc-synthetic-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis())
            .unwrap_or(0)
    ));
    std::fs::create_dir_all(&p).expect("temp dir");
    p
}

#[test]
fn synthetic_take_is_self_describing() {
    let Some(ffmpeg) = find_ffmpeg() else {
        eprintln!("skipped: no ffmpeg on this machine");
        return;
    };
    let root = temp_root();
    let mut settings = Settings::default();
    settings.fps = 30;
    settings.out_width = 640;

    let cfg = RecorderConfig {
        mon: IRect::new(0, 0, 1280, 720),
        out_root: root.clone(),
        settings,
        record_master: false,
        synthetic: true,
        audio_system: false,
        audio_mic: false,
        ..RecorderConfig::default()
    };

    let rec = match Recorder::start(cfg, ffmpeg) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("skipped: recorder did not start ({e})");
            return;
        }
    };
    std::thread::sleep(Duration::from_millis(900));
    let out_dir = rec.out_dir.clone();
    let sum = rec.stop().expect("stop should succeed");

    // A take nobody can load is a take that was lost, so start there.
    let clip = mc_engine::clip::load_clip(&out_dir).expect("meta.json should load back");
    assert!(clip.frame_count > 0, "no frames recorded");
    assert!(
        (clip.duration - sum.duration).abs() < 0.25,
        "meta says {:.2}s, recorder said {:.2}s",
        clip.duration,
        sum.duration
    );

    // track.csv is the only record of where the pointer was; a short tail means
    // the camera thread was not flushed before the take was reported finished.
    let track = std::fs::read_to_string(out_dir.join("track.csv")).expect("track.csv");
    let rows: Vec<&str> = track
        .lines()
        .filter(|l| !l.trim().is_empty() && !l.starts_with('#'))
        .collect();
    // The camera ticks at 250 Hz, so a take of D seconds should carry roughly
    // 250*D rows. Asserting a fixed count made this fail on a busy machine,
    // where the recorder's first frames take longer to come out.
    let want = (clip.duration * 100.0) as usize;
    assert!(
        rows.len() > want,
        "only {} track rows for a {:.2}s take (expected > {want})",
        rows.len(),
        clip.duration
    );
    let last_t: f64 = rows
        .last()
        .and_then(|l| l.split(',').next())
        .and_then(|s| s.trim().parse().ok())
        .expect("track time");
    assert!(
        last_t > clip.duration * 0.5,
        "track stops at {last_t:.2}s of a {:.2}s take",
        clip.duration
    );

    // frames.csv maps picture to camera tick; its rows must match the frame
    // count, header excluded.
    let frames = std::fs::read_to_string(out_dir.join("frames.csv")).expect("frames.csv");
    let frame_rows = frames
        .lines()
        .filter(|l| !l.trim().is_empty() && !l.starts_with('#'))
        .count();
    assert_eq!(
        frame_rows as i32, clip.frame_count,
        "frames.csv has {frame_rows} rows but meta says {}",
        clip.frame_count
    );

    // And the follow video has to be a real file, not a header.
    let camera = out_dir.join("camera.mp4");
    let size = std::fs::metadata(&camera).map(|m| m.len()).unwrap_or(0);
    assert!(size > 10_000, "camera.mp4 is {size} bytes");

    let _ = std::fs::remove_dir_all(&root);
}
