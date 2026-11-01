//! MouseCam engine (Rust port).
//!
//! Modules mirror the C++ implementation so behaviour can be compared
//! frame-by-frame: camera math, bilinear resampling, cursor compositing,
//! the edit list and the offline renderer all match the reference build.

pub mod camera;
pub mod capture;
pub mod clip;
pub mod log;
pub mod cursor;
pub mod edit;
pub mod ffmpeg;
pub mod hud;
pub mod single;
pub mod hud_proc;
pub mod recorder;
pub mod render;
pub mod resample;
pub mod settings;
pub mod track;

pub use camera::{CamSnapshot, Camera, IRect, Vec2};
pub use capture::{Capture, CapturePath};
pub use clip::ClipInfo;
pub use edit::{parse_edit, EditList, RenderOpts};
pub use recorder::{Recorder, RecorderConfig};
pub use render::{render_clip, RenderSummary};
pub use settings::Settings;
