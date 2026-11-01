import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()

old = """    use windows::Win32::System::DataExchange::{
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
    }"""
new = """    use windows::Win32::System::DataExchange::{
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
    }"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("clipboard api fixed")
