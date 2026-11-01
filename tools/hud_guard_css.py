import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
if ".is-disabled" not in s:
    s += """
/* a control that is intentionally unavailable right now */
.head-btn.is-disabled {
  opacity: .45;
  cursor: not-allowed;
}
"""
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("disabled style added")
