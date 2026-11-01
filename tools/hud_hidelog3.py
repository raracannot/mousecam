import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud_proc.rs"
s = io.open(p, encoding="utf-8").read()
start = s.index("        m if m == WM_APP + 1 => {")
end = s.index("        // The window must never take a click", start)
s = s[:start] + s[end:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("custom message removed, keep the timer")
