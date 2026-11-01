import io

# mc-engine needs the threading feature for a named mutex
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\Cargo.toml"
s = io.open(p, encoding="utf-8").read()
if "Win32_System_Threading" not in s:
    s = s.replace('"Win32_Storage_FileSystem",', '"Win32_Storage_FileSystem",\n    "Win32_System_Threading",', 1)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("threading feature added")
