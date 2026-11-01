import io
p = r"rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()
if "pub fn app_settings" not in s:
    s += '''
/// (effective output dir, configured dir or "" for the default, hw, hud)
pub fn app_settings() -> (String, String, bool, bool) {
    let st = settings();
    let effective = captures_root().display().to_string();
    (effective, st.captures_dir.unwrap_or_default(), st.hw_encode, st.hud_default)
}

pub fn set_app_settings(captures_dir: String, hw: bool, hud: bool) -> Result<(), String> {
    set_settings(captures_dir, hw, hud)
}
'''
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("settings wrappers added")
