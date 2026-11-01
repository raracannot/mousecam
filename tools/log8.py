import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for: %s" % (c, old[:120]))
    s = s.replace(old, new)

rep("pub fn record_start(edit: String, monitor: Option<i32>, hw: Option<bool>) -> Result<String, String> {",
    "pub fn record_start(edit: String, monitor: Option<i32>, hw: Option<bool>) -> Result<String, String> {\n    mc_engine::mc_info!(\"record\", \"start: monitor={:?} hw={:?}\", monitor, hw);")

rep("pub fn record_stop() -> Result<String, String> {",
    "pub fn record_stop() -> Result<String, String> {\n    mc_engine::mc_info!(\"record\", \"stop requested\");")

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("record logging added")
