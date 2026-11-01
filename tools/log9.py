import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-api\src\lib.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

def insert_after(header_pred, text):
    """Insert `text` (list of lines) after the line that opens the function."""
    for i, l in enumerate(lines):
        if header_pred(l):
            # find the line ending with "{" (the signature may span lines)
            j = i
            while not lines[j].rstrip().endswith("{"):
                j += 1
                if j - i > 12:
                    raise SystemExit("no opening brace for: " + l)
            lines[j+1:j+1] = text
            return True
    return False

assert insert_after(lambda l: l.startswith("pub fn record_start("),
    ['    mc_engine::mc_info!("record", "start: monitor={:?} hw={:?}", monitor, hw);'])
assert insert_after(lambda l: l.startswith("pub fn record_stop()"),
    ['    mc_engine::mc_info!("record", "stop requested");'])
assert insert_after(lambda l: l.startswith("pub fn export("),
    ['    mc_engine::mc_info!("export", "{} -> {} format={:?}", dir, out, format);'])

io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("lifecycle logging inserted")
