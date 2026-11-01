import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\Cargo.toml"
s = io.open(p, encoding="utf-8").read()
old = '"Win32_UI_WindowsAndMessaging", "Win32_UI_Shell"]'
new = '"Win32_UI_WindowsAndMessaging", "Win32_UI_Shell", "Win32_System_DataExchange", "Win32_System_Memory"]'
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("clipboard features added")

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()

old_open = """    shell_open(&p)
}"""
new_open = """    if shell_open(&p).is_ok() {
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
        CloseClipboard, EmptyClipboard, OpenClipboard, SetClipboardData, CF_UNICODETEXT,
    };
    use windows::Win32::System::Memory::{GlobalAlloc, GlobalLock, GlobalUnlock, GMEM_MOVEABLE};
    unsafe {
        let wide: Vec<u16> = text.encode_utf16().chain(std::iter::once(0)).collect();
        let bytes = wide.len() * std::mem::size_of::<u16>();
        let h = GlobalAlloc(GMEM_MOVEABLE, bytes);
        if h.is_invalid() {
            return false;
        }
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
        let ok = SetClipboardData(CF_UNICODETEXT.0 as u32, Some(HANDLE(h.0))).is_ok();
        let _ = CloseClipboard();
        ok
    }
}"""
assert s.count(old_open) >= 1
s = s.replace(old_open, new_open, 1)
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("clipboard fallback wired")
