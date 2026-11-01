import io
p = r"E:\RAYS\Desktop\workspace\mousecam\tools\verify-recpreview.mjs"
s = io.open(p, encoding="utf-8").read()
old = "return !!(im.src && im.src.startsWith('data:image') && im.naturalWidth > 0); })()`;"
new = "// the frame may arrive as a data URL or as a preview file served over the\n      // asset protocol; what matters is that an image is actually decoded\n      return !!(im.src && (im.src.startsWith('data:image') || im.src.includes('.preview')) && im.naturalWidth > 0); })()`;"
n = s.count(old)
assert n == 2, n
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("assertions updated for the file transport")
