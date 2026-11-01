import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\recorder.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:90]))
    s = s.replace(old, new)

# meta.json is written even on failure: without it the folder is invisible in
# the library, which is how a whole take disappears.
rep("""    let master_code = master.map(|m| m.finish()).unwrap_or(0);
    let code = camera.finish();
    if let Some(why) = write_err {
        return Err(format!("{why}（本次录制已中断，文件可能不完整）"));
    }
    if master_code != 0 {
        return Err(format!("原片编码器异常退出 ({master_code})"));
    }
    if code != 0 {
        return Err(format!("跟拍编码器异常退出 ({code})"));
    }

    let _ = std::fs::write(
        out_dir.join("meta.json"),
        meta_json(&cfg, elapsed, written),
    );""",
"""    let master_code = master.map(|m| m.finish()).unwrap_or(0);
    let code = camera.finish();

    let mut failure = write_err;
    if failure.is_none() && master_code != 0 {
        failure = Some(format!("原片编码器异常退出 ({master_code})"));
    }
    if failure.is_none() && code != 0 {
        failure = Some(format!("跟拍编码器异常退出 ({code})"));
    }

    // Written either way: a folder without meta.json is invisible in the
    // library, so a failed take would silently vanish and be unrecoverable.
    let mut meta = meta_json(&cfg, elapsed, written);
    if failure.is_some() {
        meta = meta.replacen("  \\"frames\\":", "  \\"complete\\": false,\\n  \\"frames\\":", 1);
    }
    if let Err(e) = std::fs::write(out_dir.join("meta.json"), &meta) {
        crate::mc_error!("rec", "写 meta.json 失败: {e}");
    }
    if let Some(why) = failure {
        return Err(format!("{why}（本次录制已中断，文件可能不完整）"));
    }""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("meta.json always written")
