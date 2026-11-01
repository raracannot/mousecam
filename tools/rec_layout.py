import io

# ---------- CSS: scope the row templates per page ----------
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
old = "  grid-template-rows: minmax(120px, 1fr) 8px var(--tl-h, 104px) 8px var(--params-h, 176px);"
new = """  /* the two pages have different children, so the rows are per page */
  grid-template-rows: minmax(120px, 1fr) auto auto;"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)

anchor = ".stage.is-hidden { display: none; }"
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + """

/* editor: viewports / timeline / params, both dividers draggable */
#stageEdit {
  grid-template-rows: minmax(120px, 1fr) 8px var(--tl-h, 104px) 8px var(--params-h, 176px);
}

/* recorder: preview / control bar / params */
#stageRecord {
  grid-template-rows: minmax(140px, 1fr) auto 8px var(--rec-params-h, 210px);
}""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("per-page row templates")

# ---------- markup: a handle above the recorder params ----------
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\index.html"
lines = io.open(p, encoding="utf-8").read().split("\n")
rec_i = next(i for i, l in enumerate(lines) if 'id="stageRecord"' in l)
params_i = next(i for i in range(rec_i, len(lines)) if '<section class="params">' in lines[i])
ind = lines[params_i][:len(lines[params_i]) - len(lines[params_i].lstrip())]
lines[params_i:params_i] = [
    ind + '<div class="split split-h" id="splitRecParams" title="拖动调整参数区高度"></div>',
    "",
]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("recorder handle inserted")
