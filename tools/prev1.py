import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# 1) expose the raw JPEG bytes
rep("""fn encode_jpeg(bgra: &[u32], w: u32, h: u32, quality: u8) -> Result<String, String> {""",
"""fn encode_jpeg_bytes(bgra: &[u32], w: u32, h: u32, quality: u8) -> Result<Vec<u8>, String> {""")
rep("""    Ok(format!(
        "data:image/jpeg;base64,{}",
        base64::engine::general_purpose::STANDARD.encode(out.into_inner())
    ))
}""",
"""    Ok(out.into_inner())
}

fn encode_jpeg(bgra: &[u32], w: u32, h: u32, quality: u8) -> Result<String, String> {
    let bytes = encode_jpeg_bytes(bgra, w, h, quality)?;
    Ok(format!(
        "data:image/jpeg;base64,{}",
        base64::engine::general_purpose::STANDARD.encode(bytes)
    ))
}

fn preview_shot() -> Result<mc_engine::recorder::PreviewShot, String> {
    let from_rec = {
        let g = session().lock().unwrap();
        g.as_ref()
            .and_then(|s| s.sink.lock().ok().and_then(|x| x.clone()))
    };
    match from_rec {
        Some(s) => Ok(s),
        None => {
            let g = preview().lock().unwrap();
            g.as_ref()
                .and_then(|e| e.sink.lock().ok().and_then(|x| x.clone()))
                .ok_or_else(|| "预览尚未就绪".to_string())
        }
    }
}

/// Writes the preview frame to a file and returns its path. Shipping a 60 KB
/// base64 string through the IPC channel ten times a second is what an
/// equivalent recorder (Cap) avoids: the webview can load a file itself, so the
/// transport carries a path instead of the picture. Two names are alternated so
/// the browser cannot serve a cached copy.
pub fn preview_frame_path() -> Result<String, String> {
    let shot = preview_shot()?;
    let bytes = encode_jpeg_bytes(&shot.px, shot.w, shot.h, 82)?;
    static TICK: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);
    let n = TICK.fetch_add(1, std::sync::atomic::Ordering::Relaxed) & 1;
    let dir = std::env::temp_dir().join("MouseCam");
    let _ = std::fs::create_dir_all(&dir);
    let path = dir.join(format!("preview-{n}.jpg"));
    std::fs::write(&path, &bytes).map_err(|e| format!("写入预览失败: {e}"))?;
    Ok(path.display().to_string())
}""")

# 2) reuse the shared lookup in preview_frame
rep("""pub fn preview_frame() -> Result<String, String> {
    let from_rec = {
        let g = session().lock().unwrap();
        g.as_ref()
            .and_then(|s| s.sink.lock().ok().and_then(|x| x.clone()))
    };
    let shot = match from_rec {
        Some(s) => s,
        None => {
            let g = preview().lock().unwrap();
            g.as_ref()
                .and_then(|e| e.sink.lock().ok().and_then(|x| x.clone()))
                .ok_or("预览尚未就绪")?
        }
    };
    encode_jpeg(&shot.px, shot.w, shot.h, 82)
}""",
"""pub fn preview_frame() -> Result<String, String> {
    let shot = preview_shot()?;
    encode_jpeg(&shot.px, shot.w, shot.h, 82)
}""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("file-based preview added")
