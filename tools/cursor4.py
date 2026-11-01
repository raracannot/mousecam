import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\camera.rs"
lines = io.open(p, encoding="utf-8").read().split("\n")

# pull the helper out from between the derive and the struct
start = next(i for i, l in enumerate(lines) if l.startswith("/// How much the viewport is currently grown"))
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "}" and "growth_factor" in "".join(lines[start:i]))
helper = lines[start:end+1]
del lines[start:end+2]          # helper + the blank line that followed it

# put it after the struct definition instead
struct_end = next(i for i, l in enumerate(lines) if l.strip() == "pub struct CamSnapshot {")
close = next(i for i in range(struct_end, len(lines)) if lines[i].strip() == "}")
lines[close+1:close+1] = [""] + helper
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("helper moved below the struct")
