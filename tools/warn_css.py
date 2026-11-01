import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
lines = io.open(p, encoding="utf-8").read().split("\n")
i = next(i for i, l in enumerate(lines) if l.strip().startswith(".fhint {"))
lines[i+1:i+1] = ["/* reports a real problem, not just information */",
                  ".fhint.is-warn { color: #f0b45a; }"]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("warn rule inserted after line", i+1)
