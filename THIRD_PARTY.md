# 第三方组件与许可证义务

MouseCam 自身是专有软件（见 LICENSE）。随包分发或链接的第三方组件如下，各自仍受其原始许可证约束。

## 1. ffmpeg（随包附带 `ffmpeg.exe`）

**当前使用的构建包含 `libx264` 与 `libx265`，这两个库是 GPL v2+。**
把 GPL 组件与专有程序一起分发时，GPL 的义务落在**该组件**上：必须随二进制提供对应源码，或提供有效期内的书面获取承诺（GPL v2 §3）。

可选的处理方式，按代价从低到高：

| 方案 | 说明 | 影响 |
|---|---|---|
| 随包附上 ffmpeg 源码 / 提供下载链接 | 最简单，满足 GPL v2 §3 | 安装包或下载页要多一个源码包 |
| 换 **LGPL** 构建的 ffmpeg（`--disable-gpl`，去掉 x264/x265） | 只需提供 ffmpeg 自身的源码与构建说明，不传染主程序 | 失去 `libx264` / `libx265` 软件编码，H.264/H.265 只能走 NVENC 或系统编码器 |
| 改用进程内 Media Foundation 编码 | 无 GPL 组件，可省掉 77 MB 的 ffmpeg.exe | 需要自己补齐 VP9 / ProRes / GIF 等格式矩阵 |

此外 H.264 / H.265 还涉及 **MPEG-LA 专利池**，商业分发通常需要评估（多数桌面录屏产品通过操作系统自带的编解码器规避）。

## 2. WebView2 Runtime（微软）

- 由 Microsoft Edge WebView2 提供，按微软的 **WebView2 Runtime 许可条款**分发。
- 安装包目前使用 Tauri 默认的 `downloadBootstrapper`（联网安装）。如果要在离线环境安装，应在 `tauri.conf.json` 里改为 `offlineInstaller`，并确认随包分发的体积与条款。

## 3. Rust / Tauri 依赖

均为宽松许可证（MIT / Apache-2.0 / BSD）。发布前建议生成一份完整的依赖声明：

```bat
cargo install cargo-about
cargo about generate about.hbs > THIRD_PARTY_RUST.md
```

## 4. 图标与字体

`rust/mc-app/icons/` 下的图标为本项目自有资源。若界面中使用了第三方字体或图标集，需在此处补登其许可证。

---

## 发布前检查清单

- [ ] 选定 ffmpeg 的分发策略（附源码 / 换 LGPL 构建 / 换 Media Foundation）
- [ ] 若使用 LGPL 构建，确认导出格式矩阵仍然满足用户需求（H.264 是否只保留 NVENC）
- [ ] 生成 Rust 依赖的第三方声明
- [ ] 在安装包的 `licenseFile` 中引用本文件或 EULA
- [ ] 代码签名证书（EV）——未签名的可执行文件会被 SmartScreen 与部分安全软件拦截
