//! Local demo server: serves the same UI as the Tauri shell and exposes the
//! same command surface over HTTP. Exists because WebView2 is blocked in some
//! locked-down environments; the front-end code is identical either way.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::sync::Arc;

fn ui_dir() -> PathBuf {
    if let Ok(d) = std::env::var("MC_UI") {
        return PathBuf::from(d);
    }
    // next to the binary, then up a few levels
    if let Ok(exe) = std::env::current_exe() {
        let mut p = exe;
        for _ in 0..8 {
            p.pop();
            for cand in ["ui", "mc-app/ui", "rust/mc-app/ui"] {
                let c = p.join(cand);
                if c.join("index.html").is_file() {
                    return c;
                }
            }
        }
    }
    // build-time location
    let m = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    m.parent().unwrap_or(&m).join("mc-app").join("ui")
}

fn mime(path: &str) -> &'static str {
    if path.ends_with(".css") {
        "text/css; charset=utf-8"
    } else if path.ends_with(".js") {
        "text/javascript; charset=utf-8"
    } else if path.ends_with(".svg") {
        "image/svg+xml"
    } else {
        "text/html; charset=utf-8"
    }
}

fn send(stream: &mut TcpStream, status: &str, ctype: &str, body: &[u8]) {
    let head = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {ctype}\r\nContent-Length: {}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n",
        body.len()
    );
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(body);
    let _ = stream.flush();
}

fn json_error(stream: &mut TcpStream, msg: &str) {
    let body = serde_json::json!({ "ok": false, "error": msg }).to_string();
    send(stream, "200 OK", "application/json; charset=utf-8", body.as_bytes());
}

fn json_ok(stream: &mut TcpStream, v: serde_json::Value) {
    let body = serde_json::json!({ "ok": true, "data": v }).to_string();
    send(stream, "200 OK", "application/json; charset=utf-8", body.as_bytes());
}

fn get_str(v: &serde_json::Value, k: &str) -> String {
    v.get(k).and_then(|x| x.as_str()).unwrap_or("").to_string()
}
fn get_i32(v: &serde_json::Value, k: &str, d: i32) -> i32 {
    v.get(k).and_then(|x| x.as_i64()).map(|x| x as i32).unwrap_or(d)
}

fn get_opt_i32(v: &serde_json::Value, k: &str) -> Option<i32> {
    v.get(k).and_then(|x| x.as_i64()).map(|x| x as i32)
}
fn get_u32(v: &serde_json::Value, k: &str, d: u32) -> u32 {
    v.get(k).and_then(|x| x.as_u64()).map(|x| x as u32).unwrap_or(d)
}

fn dispatch(name: &str, args: &serde_json::Value) -> Result<serde_json::Value, String> {
    macro_rules! s {
        ($v:expr) => {
            serde_json::to_value($v).map_err(|e| e.to_string())?
        };
    }
    match name {
        "list_clips" => Ok(s!(mc_api::list_clips())),
        "open_clip" => Ok(s!(mc_api::open_clip(get_str(args, "dir"))?)),
        "api_bake" => Ok(s!(mc_api::api_bake(get_str(args, "dir"), get_str(args, "edit"))?)),
        "track_points" => Ok(s!(mc_api::track_points(get_str(args, "dir"))?)),
        "still" => Ok(s!(mc_api::still(
            get_str(args, "dir"),
            get_str(args, "edit"),
            get_i32(args, "frame", 0),
            get_u32(args, "maxW", 900),
            get_str(args, "kind"),
        )?)),
        "record_start" => Ok(s!(mc_api::record_start(get_str(args, "edit"), get_opt_i32(args, "monitor"), args.get("hw").and_then(|v| v.as_bool()))?)),
        "record_stop" => Ok(s!(mc_api::record_stop()?)),
        "record_status" => Ok(s!(mc_api::record_status())),
        "render_proxy" => Ok(s!(mc_api::render_proxy(
            get_str(args, "dir"),
            get_str(args, "edit"),
            get_u32(args, "height", 480),
        )?)),
        "preview_start" => Ok(s!(mc_api::preview_start(get_str(args, "edit"), get_opt_i32(args, "monitor"))?)),
        "preview_stop" => { mc_api::preview_stop(); Ok(serde_json::json!(null)) }
        "preview_set_params" => { mc_api::preview_set_params(get_str(args, "edit")); Ok(serde_json::json!(null)) }
        "preview_frame" => Ok(s!(mc_api::preview_frame()?)),
        "list_monitors" => Ok(s!(mc_api::list_monitors())),
        "hud_set" => { mc_api::hud_set(args.get("enabled").and_then(|v| v.as_bool()).unwrap_or(true)); Ok(serde_json::json!(null)) }
        "hud_get" => Ok(s!(mc_api::hud_get())),
        "media_path" => Ok(s!(mc_api::media_path(
            get_str(args, "dir"),
            get_str(args, "which"),
        )?)),
        "export" => Ok(s!(mc_api::export(get_str(args, "dir"), get_str(args, "edit"), get_str(args, "out"), args.get("format").and_then(|v| v.as_str()).map(|x| x.to_string()), get_opt_i32(args, "quality"), get_opt_i32(args, "width"), get_opt_i32(args, "fps"))?)),
        other => Err(format!("unknown command: {other}")),
    }
}

fn url_decode(s: &str) -> String {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            b'%' if i + 2 < b.len() => {
                let hex = std::str::from_utf8(&b[i + 1..i + 3]).unwrap_or("");
                if let Ok(v) = u8::from_str_radix(hex, 16) {
                    out.push(v);
                    i += 3;
                    continue;
                }
                out.push(b[i]);
                i += 1;
            }
            b'+' => { out.push(b' '); i += 1; }
            c => { out.push(c); i += 1; }
        }
    }
    String::from_utf8_lossy(&out).to_string()
}

fn serve_media(stream: &mut TcpStream, file: &str, range: &str) {
    use std::io::Seek;
    let path = std::path::Path::new(file);
    let mut f = match std::fs::File::open(path) {
        Ok(f) => f,
        Err(_) => {
            send(stream, "404 Not Found", "text/plain", b"no such media");
            return;
        }
    };
    let total = match f.metadata() {
        Ok(m) => m.len(),
        Err(_) => return,
    };

    let mut start = 0u64;
    let mut end = total.saturating_sub(1);
    let mut partial = false;
    if let Some(spec) = range.strip_prefix("bytes=") {
        partial = true;
        let mut it = spec.split('-');
        if let Some(a) = it.next() {
            if !a.is_empty() {
                start = a.parse().unwrap_or(0);
            }
        }
        if let Some(b) = it.next() {
            if !b.is_empty() {
                end = b.parse().unwrap_or(end);
            }
        }
        end = end.min(total.saturating_sub(1));
        if start > end {
            start = 0;
        }
    }

    let len = end.saturating_sub(start) + 1;
    let head = if partial {
        format!(
            "HTTP/1.1 206 Partial Content\r\nContent-Type: video/mp4\r\nContent-Length: {len}\r\nContent-Range: bytes {start}-{end}/{total}\r\nAccept-Ranges: bytes\r\nConnection: close\r\n\r\n"
        )
    } else {
        format!(
            "HTTP/1.1 200 OK\r\nContent-Type: video/mp4\r\nContent-Length: {len}\r\nAccept-Ranges: bytes\r\nConnection: close\r\n\r\n"
        )
    };
    let _ = stream.write_all(head.as_bytes());

    if f.seek(std::io::SeekFrom::Start(start)).is_err() {
        return;
    }
    let mut remaining = len;
    let mut buf = vec![0u8; 256 * 1024];
    while remaining > 0 {
        let want = buf.len().min(remaining as usize);
        match std::io::Read::read(&mut f, &mut buf[..want]) {
            Ok(0) => break,
            Ok(n) => {
                if stream.write_all(&buf[..n]).is_err() {
                    break;
                }
                remaining -= n as u64;
            }
            Err(_) => break,
        }
    }
}

fn handle(mut stream: TcpStream, ui: Arc<PathBuf>) {
    let mut reader = BufReader::new(match stream.try_clone() {
        Ok(s) => s,
        Err(_) => return,
    });

    let mut line = String::new();
    if reader.read_line(&mut line).is_err() {
        return;
    }
    let mut parts = line.split_whitespace();
    let method = parts.next().unwrap_or("").to_string();
    let path = parts.next().unwrap_or("/").to_string();

    let mut content_len = 0usize;
    let mut range_hdr = String::new();
    loop {
        let mut h = String::new();
        match reader.read_line(&mut h) {
            Ok(0) => break,
            Ok(_) => {
                if h == "\r\n" || h == "\n" {
                    break;
                }
                let lower = h.to_ascii_lowercase();
                if let Some(v) = lower.strip_prefix("content-length:") {
                    content_len = v.trim().parse().unwrap_or(0);
                } else if let Some(v) = lower.strip_prefix("range:") {
                    let _ = v;
                    range_hdr = h.split(':').nth(1).unwrap_or("").trim().to_string();
                }
            }
            Err(_) => return,
        }
    }

    if method == "POST" && path.starts_with("/api/") {
        let mut body = vec![0u8; content_len];
        if content_len > 0 && reader.read_exact(&mut body).is_err() {
            return;
        }
        let args: serde_json::Value = serde_json::from_slice(&body).unwrap_or(serde_json::json!({}));
        let name = path.trim_start_matches("/api/").to_string();
        match dispatch(&name, &args) {
            Ok(v) => json_ok(&mut stream, v),
            Err(e) => json_error(&mut stream, &e),
        }
        return;
    }

    // ---- static
    let rel = if path == "/" { "/index.html".to_string() } else { path.clone() };
    let rel = rel.split('?').next().unwrap_or("").to_string();
    let file = ui.join(rel.trim_start_matches('/'));
    match std::fs::read(&file) {
        Ok(bytes) => send(&mut stream, "200 OK", mime(&rel), &bytes),
        Err(_) => send(&mut stream, "404 Not Found", "text/plain", b"not found"),
    }
}

fn main() {
    let port: u16 = std::env::var("MC_PORT").ok().and_then(|s| s.parse().ok()).unwrap_or(8765);
    let ui = Arc::new(ui_dir());
    println!("UI      {}", ui.display());
    println!("captures {}", mc_api::captures_root().display());

    let listener = match TcpListener::bind(("127.0.0.1", port)) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("端口 {port} 绑定失败: {e}");
            std::process::exit(1);
        }
    };
    println!("MouseCam demo running at http://127.0.0.1:{port}");

    for stream in listener.incoming() {
        if let Ok(s) = stream {
            let ui = ui.clone();
            std::thread::spawn(move || handle(s, ui));
        }
    }
}
