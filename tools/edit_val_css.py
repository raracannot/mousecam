import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
if ".row-val-edit" not in s:
    marker = ".toast {"
    add = """.row-val {
  cursor: text;
  user-select: none;
}
.row-val-edit {
  width: 100%;
  min-width: 46px;
  padding: 1px 4px;
  font: inherit;
  font-variant-numeric: tabular-nums;
  text-align: right;
  color: var(--fg);
  background: var(--bg-2);
  border: 1px solid var(--accent);
  border-radius: 4px;
  outline: none;
}

.toast {"""
    s = s.replace(marker, add, 1)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("editor styling added")
