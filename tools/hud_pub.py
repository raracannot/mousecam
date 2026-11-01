import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
s = s.replace("struct Surface {", "pub(crate) struct Surface {", 1)
s = s.replace("    unsafe fn new(w: i32, h: i32) -> Option<Surface> {",
              "    pub(crate) unsafe fn new(w: i32, h: i32) -> Option<Surface> {", 1)
s = s.replace("unsafe fn paint(\n    hwnd: windows::Win32::Foundation::HWND,",
              "pub(crate) unsafe fn paint(\n    hwnd: windows::Win32::Foundation::HWND,", 1)
# expose the config type and the window-creation parameters the child needs
s = s.replace("pub struct HudConfig {", "pub struct HudConfig {", 1)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("Surface/paint exposed to the crate")
