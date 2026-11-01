import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\Cargo.toml"
s = io.open(p, encoding="ascii").read()
if "opt-level = 1" not in s:
    s = s.replace("""# Debug builds stay debuggable (symbols, assertions) but the engine's hot loops
# are optimised: at opt-level 0 the 2560x1440 resampling is ~20x slower and
# makes every recording look broken for performance reasons that are not bugs.
[profile.dev.package.mc-engine]""",
"""# A debug build must stay usable: at opt-level 0 the preview round trip was
# 48 ms instead of 19 and recording cost 70% of a core instead of 42, which
# reads as "the app got laggy" when nothing in the code did. Dependencies keep
# debug symbols and assertions; only the optimisation level moves.
[profile.dev]
opt-level = 1
debug = true

[profile.dev.package.mc-engine]""")
    io.open(p, "w", encoding="ascii", newline="").write(s)
    print("dev profile raised to opt-level 1")
else:
    print("already set")
