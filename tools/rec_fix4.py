import io

# feature for GetDiskFreeSpaceExW
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\Cargo.toml"
s = io.open(p, encoding="utf-8").read()
if "Win32_Storage_FileSystem" not in s:
    s = s.replace('"Win32_System_LibraryLoader",', '"Win32_System_LibraryLoader",\n    "Win32_Storage_FileSystem",', 1)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("feature added")

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\recorder.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:80]))
    s = s.replace(old, new)

# helper
rep("""/// Same rounding rules as `Camera::source_rect`""",
"""/// Free space on the volume that holds `path`, in MB.
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

/// Same rounding rules as `Camera::source_rect`""")

# refuse to start on a nearly full disk
rep("""    let mut write_err: Option<String> = None;""",
"""    let mut write_err: Option<String> = None;
    // A full disk is the most common way a long recording dies, and ffmpeg only
    // says so after the file is already damaged.
    if let Some(mb) = free_space_mb(out_dir) {
        if mb < 500 {
            return Err(format!("磁盘空间不足（剩余 {mb} MB）"));
        }
    }""")

# re-check while recording
rep("""        if write_err.is_some() {
            break;
        }""",
"""        if written % 300 == 0 && write_err.is_none() {
            if let Some(mb) = free_space_mb(out_dir) {
                if mb < 200 {
                    write_err = Some(format!("磁盘空间不足（剩余 {mb} MB）"));
                }
            }
        }
        if write_err.is_some() {
            break;
        }""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("disk guard installed")
