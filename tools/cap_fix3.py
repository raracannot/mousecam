import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\capture.rs"
s = io.open(p, encoding="utf-8").read()

start = s.index("    pub fn open(mon: IRect) -> Result<Self, String> {")
end = s.index("    pub fn rect(&self) -> IRect {", start)
new = '''    pub fn open(mon: IRect) -> Result<Self, String> {
        if mon.w <= 0 || mon.h <= 0 {
            return Err("显示器矩形无效".into());
        }
        let mut cap = if let Some(dda) = Dda::open(mon) {
            Self {
                mon,
                dda: Some(dda),
                blt: None,
                path: CapturePath::Duplication,
                fails: 0,
            }
        } else if let Some(blt) = BitbltCap::open(mon) {
            Self {
                mon,
                dda: None,
                blt: Some(blt),
                path: CapturePath::BitBlt,
                fails: 0,
            }
        } else {
            return Err("无法初始化抓屏（DXGI 与 BitBlt 都失败）".into());
        };

        // A desktop running HDR or 10-bit colour hands back a surface we cannot
        // map. Refusing here is the only honest option: silencing it records a
        // frozen picture for the entire session.
        if cap.dda.is_some() {
            cap.probe_format(260);
            if let Some(code) = cap.format_problem() {
                return Err(format!(
                    "显示器色彩格式不支持（HDR 或 10bit，format=0x{code:X}）。请在 Windows 设置中关闭 HDR 后重试。"
                ));
            }
        }
        Ok(cap)
    }

    /// Grabs for up to `timeout_ms` looking for a surface format we cannot read.
    fn probe_format(&mut self, timeout_ms: u64) {
        let mut buf = vec![0u32; (self.mon.w as usize) * (self.mon.h as usize)];
        let deadline = std::time::Instant::now() + std::time::Duration::from_millis(timeout_ms);
        loop {
            self.grab(&mut buf);
            if self.format_problem().is_some() {
                return;
            }
            if self.dda.as_ref().map(|d| d.have_frame).unwrap_or(true) {
                return;
            }
            if std::time::Instant::now() >= deadline {
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(30));
        }
    }

    /// The surface format the desktop gave us, when it is one we cannot map.
    pub fn format_problem(&self) -> Option<u32> {
        self.dda.as_ref().and_then(|d| d.unsupported_format)
    }

'''
s = s[:start] + new + s[end:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("format probe wired into open()")
