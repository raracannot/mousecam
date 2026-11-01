import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\recorder.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

m_idx = [i for i, l in enumerate(lines) if l.strip() == "let _ = m.write_frame(&frame_buf);"]
c_idx = [i for i, l in enumerate(lines) if l.strip() == "let _ = camera.write_frame(&crop_buf);"]
assert len(m_idx) == 2 and len(c_idx) == 2, (len(m_idx), len(c_idx))

def indent_of(i):
    return lines[i][:len(lines[i]) - len(lines[i].lstrip())]

# main path: master + camera
i = m_idx[0]
ind = indent_of(i)
lines[i:i+1] = [
    ind + "if let Err(e) = m.write_frame(&frame_buf) {",
    ind + "    write_err = Some(format!(\"写入原片失败: {e}\"));",
    ind + "    break;",
    ind + "}",
]
c_idx = [k for k, l in enumerate(lines) if l.strip() == "let _ = camera.write_frame(&crop_buf);"]
i = c_idx[0]
ind = indent_of(i)
lines[i:i+1] = [
    ind + "if let Err(e) = camera.write_frame(&crop_buf) {",
    ind + "    write_err = Some(format!(\"写入跟拍成片失败: {e}\"));",
    ind + "    break;",
    ind + "}",
]

# catch-up loop: bounded, and a failed write stops the loop
c_idx = [k for k, l in enumerate(lines) if l.strip() == "let _ = camera.write_frame(&crop_buf);"]
m_idx = [k for k, l in enumerate(lines) if l.strip() == "let _ = m.write_frame(&frame_buf);"]
i = m_idx[0]
ind = indent_of(i)
lines[i:i+1] = [
    ind + "if let Err(e) = m.write_frame(&frame_buf) {",
    ind + "    write_err = Some(format!(\"写入原片失败: {e}\"));",
    ind + "    break;",
    ind + "}",
]
c_idx = [k for k, l in enumerate(lines) if l.strip() == "let _ = camera.write_frame(&crop_buf);"]
i = c_idx[0]
ind = indent_of(i)
lines[i:i+1] = [
    ind + "if let Err(e) = camera.write_frame(&crop_buf) {",
    ind + "    write_err = Some(format!(\"写入跟拍成片失败: {e}\"));",
    ind + "    break;",
    ind + "}",
]

s = "\n".join(lines)

# declare the error slot
s = s.replace("    let mut dropped = 0;", "    let mut write_err: Option<String> = None;\n    let mut dropped = 0;", 1)

# cap the catch-up: at most two seconds of duplicates
s = s.replace("        while emitted < ideal {",
"""        // A slept/timed-out loop must not try to catch up hours of frames: cap
        // the burst at two seconds and let the timeline record the gap.
        let catch_up_cap = emitted + (fps as i64) * 2;
        while emitted < ideal && emitted < catch_up_cap {""", 1)

# stop after the loop when a write failed
s = s.replace("""        let now = Instant::now();
        if now < next {""",
"""        if write_err.is_some() {
            break;
        }

        let now = Instant::now();
        if now < next {""", 1)

# check the master encoder too, and report a failed session
s = s.replace("""    if let Some(m) = master {
        m.finish();
    }
    let code = camera.finish();
    if code != 0 {
        return Err(format!("camera 缂栫爜鍣ㄥ紓甯搁€€鍑?({code})"));
    }""",
"""    let master_code = master.map(|m| m.finish()).unwrap_or(0);
    let code = camera.finish();
    if let Some(why) = write_err {
        return Err(format!("{why}（本次录制已中断，文件可能不完整）"));
    }
    if master_code != 0 {
        return Err(format!("原片编码器异常退出 ({master_code})"));
    }
    if code != 0 {
        return Err(format!("跟拍编码器异常退出 ({code})"));
    }""", 1)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("write/finish failures now fail the recording")
