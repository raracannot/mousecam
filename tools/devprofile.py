import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\Cargo.toml"
s = io.open(p, encoding="ascii").read()
if "profile.dev.package" not in s:
    s += '''
# Debug builds stay debuggable (symbols, assertions) but the engine's hot loops
# are optimised: at opt-level 0 the 2560x1440 resampling is ~20x slower and
# makes every recording look broken for performance reasons that are not bugs.
[profile.dev.package.mc-engine]
opt-level = 2

[profile.dev.package.mc-api]
opt-level = 2
'''
    io.open(p, "w", encoding="ascii", newline="").write(s)
    print("dev profile overrides added")
