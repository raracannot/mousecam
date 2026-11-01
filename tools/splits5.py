import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\index.html"
lines = io.open(p, encoding="utf-8").read().split("\n")

# 1) drop the stray handle that landed in the record page
stray = [i for i, l in enumerate(lines) if 'id="splitStageB"' in l]
assert len(stray) == 1, stray
del lines[stray[0]]

# 2) put it between the edit timeline and the edit params
first_params = next(i for i, l in enumerate(lines) if '<section class="params">' in l)
indent = lines[first_params][:len(lines[first_params]) - len(lines[first_params].lstrip())]
lines[first_params:first_params] = [
    indent + '<div class="split split-h" id="splitStageB" title="拖动调整参数区高度"></div>',
    "",
]
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(lines))
print("handle moved to the edit page")
