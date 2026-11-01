import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = """    // A path, not the picture: the engine writes the JPEG and the webview loads
    // it through the asset protocol, so the IPC channel carries ~100 bytes
    // instead of 60 KB of base64 ten times a second.
    const path = await invoke('preview_frame_path');
    const img = $('recPreview');
    const url = path ? mediaUrl(path) : '';"""
new = """    // A data URL: writing the JPEG to a file and serving it over the asset
    // protocol was measured at 23.6 ms vs 24.6 ms, so it saves no time, and the
    // browser caches the small set of filenames so the picture stops updating.
    const url = await invoke('preview_frame');
    const img = $('recPreview');"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("preview transport reverted to the data URL")
