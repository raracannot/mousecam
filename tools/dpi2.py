import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\src\main.rs"
s = io.open(p, encoding="utf-8").read()
s = s.replace("""    log_dpi_awareness();
    tauri::Builder::default()
        .setup(|app| {""", """    tauri::Builder::default()
        .setup(|app| {
            log_dpi_awareness();""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("dpi log moved into setup")
