import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
old = "                let (ww, wh) = m.len(r.w + pad * 2, r.h + pad * 2);"
assert s.count(old) == 1, s.count(old)
new = ("                let (ww, wh) = m.len(r.w + pad * 2, r.h + pad * 2);\n"
       "                // A mis-scaled window can ask for a huge size; an oversized layered\n"
       "                // window stalls composition, so keep it sane.\n"
       "                let ww = ww.clamp(1, 16384);\n"
       "                let wh = wh.clamp(1, 16384);")
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("clamp added")
