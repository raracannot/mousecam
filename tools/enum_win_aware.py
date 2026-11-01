import ctypes, ctypes.wintypes as w
u = ctypes.windll.user32
# measure in physical pixels, like the app does
u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

def info(h):
    cls = ctypes.create_unicode_buffer(128); u.GetClassNameW(h, cls, 128)
    r = w.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    pid = w.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return cls.value, r, pid.value

found = []
@ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
def cb(h, l):
    cls, r, pid = info(h)
    if cls.startswith("MouseCam"):
        found.append((cls, r, pid, bool(u.IsWindowVisible(h))))
    return True
u.EnumWindows(cb, 0)
for cls, r, pid, vis in found:
    print("%s pid=%s vis=%s rect=(%d,%d %dx%d)" % (cls, pid, vis, r.left, r.top, r.right-r.left, r.bottom-r.top))
