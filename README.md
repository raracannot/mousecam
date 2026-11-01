# MouseCam

跟随鼠标的 Windows 录屏工具。录屏时不只是录下整屏，而是**同时**产出一份自动跟随光标的裁切视口 —— 适合教程、演示、操作回放这类「观众想知道你在看哪里」的场景。

Rust + Tauri 2 + WebView2，纯 Windows。

## 三份产物

每次录制都会同时写出：

| 文件 | 内容 |
|---|---|
| `master.mp4` | 完整原片，保留全屏，供二次裁切 |
| `camera.mp4` | 跟拍成片：自动裁切、跟随光标的视口，轨迹已平滑 |
| `track.csv` | 鼠标轨迹，坐标 + 时间，**250 Hz** |

另外还有 `frames.csv`（帧 → 相机刻度映射）和 `meta.json`（本次录制参数）。素材是自描述的：一个目录就是一份可重现的工程。

## 跟拍是怎么算的

取景器在 250 Hz 上解算，与录制帧率解耦：

- **One Euro** 滤波抑制抖动，保留快速移动的跟随性
- **临界阻尼弹簧**做位置过渡，避免生硬跳切
- **速度驱动的视口放大**：鼠标移动越快，视口越大（默认 1.2 倍），让观众看到更多上下文；光标本身按视口放大的同比例补回，所以看起来是「光标变大」而不是「画面缩小」
- 前瞻量按速度提前偏移视口中心

因为结构是「先记轨迹、后渲染」，同一段 `master.mp4` 可以按不同参数反复烘焙出不同版本。

## 其它

- **取景框（HUD）**：录制前在屏幕上标出当前取景范围。它是一个独立进程（`mousecam.exe --hud`），用 `UpdateLayeredWindow` 绘制，崩溃不影响录制
- **编辑页**：裁切区间、跟随关键帧、代理预览、多格式导出（H.264 / H.265 / VP9 / ProRes / GIF）
- **参数记忆**：跟拍参数与界面分栏尺寸都会被记住
- **可观测**：轮转日志、panic hook、心跳看门狗、崩溃遗留录制自动恢复

## 快速开始

从 Releases 下载便携版，解压后双击 `mousecam.exe`。需要系统里有 WebView2 运行时（Windows 11 自带）。

## 自行构建

依赖：

- Rust（stable，MSVC 工具链）
- Node.js 22+（只为 Tauri CLI）
- Visual Studio 2022 C++ 生成工具 + Windows SDK
- WebView2 Runtime

```bat
cd rust\mc-app
npm install
npx tauri build --bundles msi
```

开发调试：

```bat
cd rust\mc-app
cargo build
```

构建出的 `mousecam.exe` 需要同目录下有 `ffmpeg.exe`（从 `dist/ffmpeg.exe` 复制过去，正式打包时会自动内联）。

## 仓库结构

```
rust/mc-engine/   采集（DXGI 复制 + GDI 兜底）、相机解算、录制管线、取景框、编辑烘焙、日志
rust/mc-api/      Tauri 命令层（会话 / 预览 / 设置）
rust/mc-app/      应用外壳（Tauri 入口、界面、打包配置）
rust/mc-server/   本地服务
tools/            自动化验证脚本（CDP 驱动界面 + 录制回归）
```

`rust/README.md` 里有更详细的架构说明。

## 已知限制

- **没有音频**：麦克风与系统声都未实现
- **HDR / 10bit 显示器**：DXGI 会返回无法映射的色彩格式，程序会在启动时明确报错，需要关闭 HDR
- **录制期间取景框自动隐藏**：桌面复制接口不理会 `WDA_EXCLUDEFROMCAPTURE`，留着会把边框录进画面
- **仅整屏录制**，暂不支持区域 / 窗口采集与暂停继续
- 未签名，首次运行可能被 SmartScreen 或安全软件拦截

## 许可证

[GPL-3.0](LICENSE)。

你可以自由使用、修改、分发本项目（包括商用），但**分发修改后的版本时必须同样以 GPL-3.0 开源**，并保留版权声明。

第三方组件与分发义务见 [THIRD_PARTY.md](THIRD_PARTY.md)。

## 参与

Issue 和 PR 都欢迎。开发环境的搭建见上面的「自行构建」，`tools/` 里有基于 CDP 的界面回归脚本，改动后建议跑一遍。
