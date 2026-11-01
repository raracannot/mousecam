import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()

anchor = "pub fn list_monitors() -> Vec<MonitorDto> {"
assert s.count(anchor) == 1
new = '''/// Adopts `rec_*` folders that have a recording but no `meta.json`, which is what
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
                "{{\\n",
                "  \\"app\\": \\"MouseCam\\",\\n",
                "  \\"recovered\\": true,\\n",
                "  \\"complete\\": false,\\n",
                "  \\"monitor\\": {{\\"x\\": {}, \\"y\\": {}, \\"w\\": {}, \\"h\\": {}}},\\n",
                "  \\"fps\\": 30,\\n",
                "  \\"outWidth\\": 1080,\\n",
                "  \\"outHeight\\": 608,\\n",
                "  \\"aspectIdx\\": 0,\\n",
                "  \\"zoom\\": 1.0,\\n",
                "  \\"duration\\": {:.6},\\n",
                "  \\"frames\\": {}\\n",
                "}}\\n"
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

pub fn list_monitors() -> Vec<MonitorDto> {'''
s = s.replace(anchor, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("recover_orphan_clips added")
