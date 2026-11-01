import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()
old = """    match p.parent() {
        Some(dir) => shell_open(dir),
        None => shell_open(&p),
    }
}"""
new = """    let opened = match p.parent() {
        Some(dir) => shell_open(dir),
        None => shell_open(&p),
    };
    if opened.is_ok() {
        return Ok(());
    }
    if copy_to_clipboard(&p.as_os_str().to_string_lossy()) {
        return Err("无法打开文件夹，路径已复制到剪贴板".into());
    }
    Err("无法打开文件夹".into())
}"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("reveal_file falls back too")
