import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
for probe in ["grid-template-rows: minmax(120px, 1fr) 8px var(--tl-h, 104px) 8px var(--params-h, 176px);",
              "grid-template-columns: var(--vp-left, 1fr) 14px minmax(0, 1fr);"]:
    print("applied:", probe[:60], "->", probe in s)
