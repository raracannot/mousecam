import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
old = """    *settings_cell().lock().unwrap() = None;
    Ok(())"""
new = """    *settings_cell().lock().unwrap() = None;
    // the capture folders depend on the setting, so resolve them again
    invalidate_captures_root();
    Ok(())"""
assert s.count(old) >= 1
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("settings change re-resolves the captures root")

p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\recorder.rs"
s = io.open(p, encoding="utf-8").read()
old = '.map_err(|e| format!("创建目录失败 {}: {e}", out_dir.display()))?;'
new = '.map_err(|e| format!("创建录制目录失败 {}: {e}（“拒绝访问”多是安全软件拦截，可在设置里换一个输出文件夹）", out_dir.display()))?;'
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("clearer failure message")
