import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\Cargo.toml"
s = io.open(p, encoding="utf-8").read()
if "Win32_Security" not in s:
    s = s.replace('"Win32_System_Threading",', '"Win32_System_Threading",\n    "Win32_Security",', 1)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("security feature added (CreateMutexW lives behind it)")
