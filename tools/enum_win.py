import ctypes, ctypes.wintypes as w
u = ctypes.windll.user32

def info(h):
    cls = ctypes.create_unicode_buffer(128); u.GetClassNameW(h, cls, 128)
    title = ctypes.create_unicode_buffer(260); u.GetWindowTextW(h, title, 260)
    r = w.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    pid = w.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return cls.value, title.value, r, pid.value

found = []
@ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
def cb(h, l):
    cls, title, r, pid = info(h)
    if cls.startswith("MouseCam"):
        found.append((h, cls, title, r, pid, bool(u.IsWindowVisible(h))))
    return True
u.EnumWindows(cb, 0)
print("overlay windows:", len(found))
for h, cls, title, r, pid, vis in found:
    print("  hwnd=%s class=%s title=%r pid=%s vis=%s rect=(%d,%d %dx%d)" % (
        h, cls, title, pid, vis, r.left, r.top, r.right-r.left, r.bottom-r.top))
