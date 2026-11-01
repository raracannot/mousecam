import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
anchor = """#stageRecord {
  grid-template-rows: minmax(140px, 1fr) auto 8px var(--rec-params-h, 210px);
}"""
assert s.count(anchor) == 1
add = anchor + """

/* the recorder params panel has three rows (head, the frame row, the grid); the
   shared rule only declares two, so the frame row was taking the 1fr and
   stretching itself across the whole panel */
#stageRecord .params {
  grid-template-rows: 32px auto minmax(0, 1fr);
}"""
s = s.replace(anchor, add)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("recorder params rows fixed")
