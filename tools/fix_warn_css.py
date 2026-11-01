import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
s = s.replace(""".set-hint.is-warn {""", """.fhint.is-warn {""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("selector fixed ->", ".fhint.is-warn" in s)
