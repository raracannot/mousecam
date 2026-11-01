import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:90]))
    s = s.replace(old, new)

# boot: restore before the grids are built so they render the saved values
rep("""(async function boot() {
  buildParams('paramsGrid');""",
"""(async function boot() {
  loadSavedParams();
  buildParams('paramsGrid');""")

# the frame row must show the restored values, not the markup defaults
i = s.index("$('hudLabel').onchange = () => {")
j = s.index("};", i) + 2
s = s[:j] + """

  // reflect whatever was restored, otherwise the row lies about the frame width
  $('hudWidth').value = hudCfg.thickness;
  $('hudWidthVal').textContent = hudCfg.thickness;
  $('hudLabel').checked = !!hudCfg.label;
  if ($('hudBrackets')) $('hudBrackets').checked = !!hudCfg.brackets;""" + s[j:]

# a reset is a choice worth remembering too
s = s.replace("""    state.edit = { ...DEFAULTS };
    buildParams('paramsGrid');""",
"""    state.edit = { ...DEFAULTS };
    saveParams();
    buildParams('paramsGrid');""")
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("boot restore + frame row sync + reset persist")
