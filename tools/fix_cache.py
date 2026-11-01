import io
p = r"rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()

# one cache, shared by the reader and the writer
old = """pub fn settings() -> AppSettings {
    static CACHE: OnceLock<Mutex<Option<AppSettings>>> = OnceLock::new();
    let cell = CACHE.get_or_init(|| Mutex::new(None));
    let mut g = cell.lock().unwrap();"""
new = """fn settings_cell() -> &'static Mutex<Option<AppSettings>> {
    static CACHE: OnceLock<Mutex<Option<AppSettings>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(None))
}

pub fn settings() -> AppSettings {
    let mut g = settings_cell().lock().unwrap();"""
assert s.count(old) == 1
s = s.replace(old, new)

old2 = """    if let Some(cell) = SETTINGS_CACHE.get() {
        *cell.lock().unwrap() = None;
    }
    Ok(())
}

static SETTINGS_CACHE: std::sync::OnceLock<Mutex<Option<AppSettings>>> = std::sync::OnceLock::new();"""
new2 = """    *settings_cell().lock().unwrap() = None;
    Ok(())
}"""
assert s.count(old2) == 1
s = s.replace(old2, new2)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("cache unified")
