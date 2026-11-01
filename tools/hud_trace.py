import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\hud.rs"
s = io.open(p, encoding="utf-8").read()
old = """            last = buf;
        }"""
new = """            if std::env::var_os("MC_HUD_TRACE").is_some() {
                crate::mc_debug!("hud", "send {}", buf.trim().replace('\\n', " | "));
            }
            last = buf;
        }"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("send trace added")
