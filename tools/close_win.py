import ctypes, ctypes.wintypes as w
u = ctypes.windll.user32
u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
found = []
@ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
def cb(h, l):
    t = ctypes.create_unicode_buffer(260); u.GetWindowTextW(h, t, 260)
    c = ctypes.create_unicode_buffer(128); u.GetClassNameW(h, c, 128)
    if t.value == "MouseCam" and u.IsWindowVisible(h):
        found.append((h, c.value))
    return True
u.EnumWindows(cb, 0)
for h, c in found:
    print("closing hwnd=%s class=%s" % (h, c))
    u.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE
