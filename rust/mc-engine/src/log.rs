//! Persistent, rotating log for diagnostics.
//!
//! One file next to the binary (`mousecam.log`), one line per event:
//!
//! ```text
//! 2026-11-01 12:06:38.123  INFO   [preview] started, monitor 1
//! 2026-11-01 12:06:39.002  ERROR  [panic] index out of bounds at hud.rs:412 (thread hud)
//! ```
//!
//! Everything that can fail silently logs through here: panics (including those
//! on background threads, which otherwise just vanish), frontend exceptions
//! forwarded over IPC, ffmpeg stderr, and the ordinary lifecycle events.

use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::sync::Mutex;

/// Rotate once past this size; a long session must not fill the disk.
pub const MAX_BYTES: u64 = 4 * 1024 * 1024;

#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Level {
    Debug,
    Info,
    Warn,
    Error,
}

impl Level {
    fn tag(self) -> &'static str {
        match self {
            Level::Debug => "DEBUG",
            Level::Info => "INFO ",
            Level::Warn => "WARN ",
            Level::Error => "ERROR",
        }
    }

    pub fn parse(s: &str) -> Level {
        match s.to_ascii_lowercase().as_str() {
            "debug" => Level::Debug,
            "warn" | "warning" => Level::Warn,
            "error" => Level::Error,
            _ => Level::Info,
        }
    }
}

struct Sink {
    file: Option<File>,
    path: PathBuf,
    verbose: bool,
    /// Key of the last message written, and how many identical ones followed.
    /// A poller that fails at 8 Hz would otherwise bury everything else.
    last: String,
    repeats: u32,
}

static SINK: OnceLock<Mutex<Sink>> = OnceLock::new();

fn cell() -> &'static Mutex<Sink> {
    SINK.get_or_init(|| {
        Mutex::new(Sink {
            file: None,
            path: PathBuf::from("mousecam.log"),
            verbose: false,
            last: String::new(),
            repeats: 0,
        })
    })
}

/// Opens the log, rotating the previous one if it has grown too large.
/// Returns false when the file could not be opened (a read-only install dir,
/// for example) so the caller can fall back to another location.
pub fn init(path: PathBuf, verbose: bool) -> bool {
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(md) = std::fs::metadata(&path) {
        if md.len() > MAX_BYTES {
            let _ = std::fs::remove_file(path.with_extension("log.1"));
            let _ = std::fs::rename(&path, path.with_extension("log.1"));
        }
    }
    let file = OpenOptions::new().create(true).append(true).open(&path).ok();
    let opened = file.is_some();
    if let Ok(mut s) = cell().lock() {
        s.file = file;
        s.path = path;
        s.verbose = verbose;
    }
    opened
}

pub fn path() -> PathBuf {
    cell().lock().map(|s| s.path.clone()).unwrap_or_default()
}

pub fn set_verbose(on: bool) {
    if let Ok(mut s) = cell().lock() {
        s.verbose = on;
    }
}

pub fn verbose() -> bool {
    cell().lock().map(|s| s.verbose).unwrap_or(false)
}

pub fn is_enabled(level: Level) -> bool {
    level != Level::Debug || verbose()
}

/// Writes one line. Never panics and never blocks for long: a broken log must
/// not take the application down with it.
pub fn log(level: Level, target: &str, msg: &str) {
    if !is_enabled(level) {
        return;
    }
    let key = format!("{}{}{}", level.tag(), target, msg);
    let mut s = match cell().lock() {
        Ok(s) => s,
        Err(_) => return,
    };

    if s.last == key {
        s.repeats = s.repeats.saturating_add(1);
        return;
    }

    let mut line = String::new();
    if s.repeats > 1 {
        line.push_str(&format!(
            "{}  {}  [{:<10}] ... 上一行又重复了 {} 次\n",
            stamp(),
            "DEBUG",
            "repeat",
            s.repeats
        ));
        s.repeats = 0;
    }
    line.push_str(&format!(
        "{}  {}  [{:<10}] {}\n",
        stamp(),
        level.tag(),
        truncate(target, 10),
        msg
    ));
    s.last = key;

    if let Some(f) = s.file.as_mut() {
        let _ = f.write_all(line.as_bytes());
        let _ = f.flush();
    }
    drop(s);
    // stderr as well, so a terminal run shows it live
    eprint!("{line}");
}

/// Same as `log`, but never waits for the sink. Used from the panic hook: if
/// the panic happened while another frame of this thread held that lock, a
/// blocking lock would hang the very thread that is trying to report it.
pub fn log_no_block(level: Level, target: &str, msg: &str) {
    let line = format!(
        "{}  {}  [{:<10}] {}\n",
        stamp(),
        level.tag(),
        truncate(target, 10),
        msg
    );
    eprint!("{line}");
    if let Ok(mut s) = cell().try_lock() {
        if let Some(f) = s.file.as_mut() {
            let _ = f.write_all(line.as_bytes());
            let _ = f.flush();
        }
    }
}

fn truncate(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        s.chars().take(n).collect()
    }
}

/// `YYYY-MM-DD HH:MM:SS.mmm` in local time.
fn stamp() -> String {
    use windows::Win32::System::SystemInformation::GetLocalTime;
    let st = unsafe { GetLocalTime() };
    format!(
        "{:04}-{:02}-{:02} {:02}:{:02}:{:02}.{:03}",
        st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond, st.wMilliseconds
    )
}

// ---------------------------------------------------------------- macros
//
// `mc_log!(Info, "preview", "started {}", n)` - target first, then format args.

#[macro_export]
macro_rules! mc_log {
    ($level:ident, $target:expr, $($arg:tt)*) => {
        if $crate::log::is_enabled($crate::log::Level::$level) {
            $crate::log::log($crate::log::Level::$level, $target, &format!($($arg)*));
        }
    };
}

#[macro_export]
macro_rules! mc_info {
    ($target:expr, $($arg:tt)*) => { $crate::mc_log!(Info, $target, $($arg)*) };
}

#[macro_export]
macro_rules! mc_warn {
    ($target:expr, $($arg:tt)*) => { $crate::mc_log!(Warn, $target, $($arg)*) };
}

#[macro_export]
macro_rules! mc_error {
    ($target:expr, $($arg:tt)*) => { $crate::mc_log!(Error, $target, $($arg)*) };
}

#[macro_export]
macro_rules! mc_debug {
    ($target:expr, $($arg:tt)*) => { $crate::mc_log!(Debug, $target, $($arg)*) };
}

/// Installs a panic hook that records the panic before the process unwinds.
/// A panic on a worker thread only kills that thread, which otherwise looks
/// exactly like "the feature silently stopped working".
pub fn install_panic_hook() {
    let default = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let loc = info
            .location()
            .map(|l| format!("{}:{}", l.file(), l.line()))
            .unwrap_or_else(|| "?".into());
        let payload = if let Some(s) = info.payload().downcast_ref::<&str>() {
            (*s).to_string()
        } else if let Some(s) = info.payload().downcast_ref::<String>() {
            s.clone()
        } else {
            "panic".to_string()
        };
        let thread = std::thread::current();
        log_no_block(
            Level::Error,
            "panic",
            &format!(
                "{} at {} (thread {})",
                payload,
                loc,
                thread.name().unwrap_or("unnamed")
            ),
        );
        default(info);
    }));
}

/// Convenience for logging a path without the quotes.
pub fn show(p: impl AsRef<Path>) -> String {
    p.as_ref().display().to_string()
}
