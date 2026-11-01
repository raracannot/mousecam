import io

def patch(path, pairs, enc="utf-8"):
    p = path
    s = io.open(p, encoding=enc).read()
    for old, new in pairs:
        c = s.count(old)
        if c != 1:
            raise SystemExit("%s: matched %d for:\n%s" % (p, c, old[:160]))
        s = s.replace(old, new)
    io.open(p, "w", encoding=enc, newline="").write(s)
    print("patched", p)

# 1) expose the module
patch(r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\lib.rs",
      [("pub mod clip;", "pub mod clip;\npub mod log;")], enc="utf-8")

# 2) verbose flag in the settings file
patch(r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs", [
("""pub struct AppSettings {
    pub captures_dir: Option<String>,
    pub hw_encode: bool,
    pub hud_default: bool,
}""",
"""pub struct AppSettings {
    pub captures_dir: Option<String>,
    pub hw_encode: bool,
    pub hud_default: bool,
    pub verbose: bool,
}"""),
("""    let mut out = AppSettings {
        captures_dir: None,
        hw_encode: true,
        hud_default: true,
    };""",
"""    let mut out = AppSettings {
        captures_dir: None,
        hw_encode: true,
        hud_default: true,
        verbose: false,
    };"""),
("""                "hud" => out.hud_default = v == "1" || v.eq_ignore_ascii_case("true"),""",
"""                "hud" => out.hud_default = v == "1" || v.eq_ignore_ascii_case("true"),
                "verbose" => out.verbose = v == "1" || v.eq_ignore_ascii_case("true"),"""),
("""pub fn set_settings(captures_dir: String, hw: bool, hud: bool) -> Result<(), String> {""",
"""pub fn set_settings(captures_dir: String, hw: bool, hud: bool, verbose: bool) -> Result<(), String> {"""),
("""    let body = format!(
        "# MouseCam \u8bbe\u7f6e\\ncaptures={}\\nhw={}\\nhud={}\\n",
        dir,
        if hw { 1 } else { 0 },
        if hud { 1 } else { 0 }
    );""",
"""    let body = format!(
        "# MouseCam \u8bbe\u7f6e\\ncaptures={}\\nhw={}\\nhud={}\\nverbose={}\\n",
        dir,
        if hw { 1 } else { 0 },
        if hud { 1 } else { 0 },
        if verbose { 1 } else { 0 }
    );"""),
("""pub fn app_settings() -> (String, String, bool, bool) {
    let st = settings();
    let effective = captures_root().display().to_string();
    (effective, st.captures_dir.unwrap_or_default(), st.hw_encode, st.hud_default)
}

pub fn set_app_settings(captures_dir: String, hw: bool, hud: bool) -> Result<(), String> {
    set_settings(captures_dir, hw, hud)
}""",
"""pub fn app_settings() -> (String, String, bool, bool, bool) {
    let st = settings();
    let effective = captures_root().display().to_string();
    (
        effective,
        st.captures_dir.unwrap_or_default(),
        st.hw_encode,
        st.hud_default,
        st.verbose,
    )
}

pub fn set_app_settings(
    captures_dir: String,
    hw: bool,
    hud: bool,
    verbose: bool,
) -> Result<(), String> {
    set_settings(captures_dir, hw, hud, verbose)
        .map_err(|e| e)
        .inspect(|_| mc_engine::log::set_verbose(verbose))
}"""),
])
