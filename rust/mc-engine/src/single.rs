use windows::core::{w, PCWSTR};
use windows::Win32::Foundation::{GetLastError, ERROR_ALREADY_EXISTS, HWND};
use windows::Win32::System::Threading::CreateMutexW;
use windows::Win32::UI::WindowsAndMessaging::{
    FindWindowW, IsIconic, SetForegroundWindow, ShowWindow, SW_RESTORE,
};

/// Claims the single-instance mutex. Returns false when this machine already runs
/// MouseCam, in which case the caller should bring that window forward and exit.
///
/// Two instances would fight over the DXGI duplication and the second one would
/// silently fall back to the slower BitBlt path, so this is a correctness guard,
/// not a nicety.
pub fn claim_single_instance() -> bool {
    unsafe {
        let _ = CreateMutexW(None, true, w!("Local\\MouseCamInstance"));
        GetLastError() != ERROR_ALREADY_EXISTS
    }
}

/// Brings an already running MouseCam to the front.
pub fn focus_existing_window() -> bool {
    unsafe {
        for title in [w!("MouseCam")] {
            if let Ok(hwnd) = FindWindowW(PCWSTR::null(), title) {
                if !hwnd.is_invalid() {
                    if IsIconic(hwnd).as_bool() {
                        let _ = ShowWindow(hwnd, SW_RESTORE);
                    }
                    let _ = SetForegroundWindow(hwnd);
                    return true;
                }
            }
        }
        // fall back to the Tauri window class when the title was changed
        if let Ok(hwnd) = FindWindowW(w!("Tauri Window"), PCWSTR::null()) {
            if !hwnd.is_invalid() {
                let _ = ShowWindow(hwnd, SW_RESTORE);
                let _ = SetForegroundWindow(hwnd);
                return true;
            }
        }
    }
    let _ = HWND::default();
    false
}
