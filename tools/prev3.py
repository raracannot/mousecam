import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

old = """async function tickRecPreview() {
  if (!state.recPreviewOn) return;
  try {
    const url = await invoke('preview_frame');
    const img = $('recPreview');
    if (url && img.src !== url) {
      img.src = url;"""
new = """async function tickRecPreview() {
  if (!state.recPreviewOn) return;
  try {
    // A path, not the picture: the engine writes the JPEG and the webview loads
    // it through the asset protocol, so the IPC channel carries ~100 bytes
    // instead of 60 KB of base64 ten times a second.
    const path = await invoke('preview_frame_path');
    const img = $('recPreview');
    const url = path ? mediaUrl(path) : '';
    if (url && img.src !== url) {
      img.src = url;"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("preview now loads from a file")
