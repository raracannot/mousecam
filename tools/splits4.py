import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
lines = io.open(p, encoding="utf-8").read().split("\n")

def set_after(marker, index_from, new_lines, expect_contains=None):
    for i in range(index_from, len(lines)):
        if marker in lines[i]:
            if expect_contains and expect_contains not in lines[i]:
                continue
            lines[i] = new_lines
            return True
    return False

assert set_after("grid-template-rows: minmax(0, 1fr) 104px 176px;", 0,
                 "  grid-template-rows: minmax(120px, 1fr) 8px var(--tl-h, 104px) 8px var(--params-h, 176px);")
assert set_after("grid-template-columns: 1fr 1fr;", 0,
                 "  grid-template-columns: var(--vp-left, 1fr) 14px minmax(0, 1fr);")
assert set_after("gap: var(--sp-3);", 0, "  gap: 0;", expect_contains="gap")
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("stage rows, viewport columns and gap updated")
