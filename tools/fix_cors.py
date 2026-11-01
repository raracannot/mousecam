import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()
old = """    const mp = await invoke('media_path', { dir, which: 'master' });
    const v = $('viewVideo');
    v.src = mediaUrl(mp);"""
new = """    const mp = await invoke('media_path', { dir, which: 'master' });
    const v = $('viewVideo');
    // Needed so the follow view can be drawn from this video without tainting
    // the canvas (a tainted canvas breaks getImageData/toDataURL).
    v.crossOrigin = 'anonymous';
    v.src = mediaUrl(mp);"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("crossOrigin set")
