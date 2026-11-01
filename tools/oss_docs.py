import io

# ---- README: license section ----
p = r"E:\RAYS\Desktop\workspace\mousecam\README.md"
s = io.open(p, encoding="utf-8").read()
old = """## 许可证

专有软件，见 [LICENSE](LICENSE)。第三方组件与分发义务见 [THIRD_PARTY.md](THIRD_PARTY.md)。"""
new = """## 许可证

[GPL-3.0](LICENSE)。

你可以自由使用、修改、分发本项目（包括商用），但**分发修改后的版本时必须同样以 GPL-3.0 开源**，并保留版权声明。

第三方组件与分发义务见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 参与

Issue 和 PR 都欢迎。开发环境的搭建见上面的「自行构建」，`tools/` 里有基于 CDP 的界面回归脚本，改动后建议跑一遍。"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("README updated")

# ---- THIRD_PARTY: GPL is now compatible with the app licence ----
p = r"E:\RAYS\Desktop\workspace\mousecam\THIRD_PARTY.md"
s = io.open(p, encoding="utf-8").read()
old_head = """MouseCam 自身是专有软件（见 LICENSE）。随包分发或链接的第三方组件如下，各自仍受其原始许可证约束。"""
new_head = """MouseCam 自身以 **GPL-3.0** 发布（见 LICENSE）。随包分发或链接的第三方组件如下，各自仍受其原始许可证约束。"""
assert s.count(old_head) == 1
s = s.replace(old_head, new_head)

old_ff = """**当前使用的构建包含 `libx264` 与 `libx265`，这两个库是 GPL v2+。**
把 GPL 组件与专有程序一起分发时，GPL 的义务落在**该组件**上：必须随二进制提供对应源码，或提供有效期内的书面获取承诺（GPL v2 §3）。

可选的处理方式，按代价从低到高："""
new_ff = """**当前使用的构建包含 `libx264` 与 `libx265`，这两个库是 GPL v2+。**

本程序同样以 GPL-3.0 发布，两者兼容，不存在授权冲突。剩下的义务只有一条：**分发二进制时提供 ffmpeg 对应的源码，或给出有效期内的书面获取承诺**（GPL v2 §3 / GPL v3 §6）。最简单的做法是在 Release 页面附上 ffmpeg 的版本与源码地址。

如果将来想放宽本程序的许可证（例如改为 MIT），这一节就会变成真正的约束，届时的处理方式："""
assert s.count(old_ff) == 1
s = s.replace(old_ff, new_ff)

old_check = """- [ ] 选定 ffmpeg 的分发策略（附源码 / 换 LGPL 构建 / 换 Media Foundation）"""
new_check = """- [ ] 在 Release 页面注明 ffmpeg 版本与源码获取方式（GPL 义务）"""
assert s.count(old_check) == 1
s = s.replace(old_check, new_check)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("THIRD_PARTY updated")
