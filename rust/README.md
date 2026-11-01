# MouseCam — Rust 引擎 + Tauri 壳

录制屏幕并生成「跟着鼠标走」的裁切视口，录制后可离线重新取景、裁切、手动改轨迹，再导出。

## 结构

```
rust/
  mc-engine/   引擎（无 UI）
    camera.rs     One Euro 滤波 + 临界阻尼弹簧 + 速度自适应视口
    capture.rs    DXGI Desktop Duplication（GDI BitBlt 回退）
    cursor.rs     光标精灵解码 + 缩放 alpha 合成
    resample.rs   双线性重采样（整数权重）
    ffmpeg.rs     ffmpeg 子进程管道
    recorder.rs   录制线程（相机独立 250Hz 时钟 + CFR 补帧）
    render.rs     离线重渲染
    edit.rs       .mcl 编辑清单（裁切 / 轨迹关键帧 / 相机参数）
    clip.rs       素材读取（meta.json / track.csv / frames.csv）
  mc-api/      命令层（两条传输共用）
  mc-app/      Tauri 壳（正式产品）
  mc-server/   本地 HTTP 服务（WebView2 不可用时的开发/演示通道）
```

前端只有一份：`mc-app/ui/`。`app.js` 顶部有一个传输层 shim，Tauri 走 IPC，浏览器走 `fetch`。

## 功能

- **屏幕上取景框**：录制页可开关，直接在桌面上用蓝框标出当前跟拍范围并显示尺寸，
  鼠标穿透、不会被录进视频（`WDA_EXCLUDEFROMCAPTURE`）
- **录制页**：顶部是跟拍视口的**实时预览**，底部是同一套跟拍参数，改参数立刻反映到预览；
  大圆钮开始、方形按钮停止；同时产出 `master.mp4`（原片）、`camera.mp4`（跟拍）、
  `track.csv`（250Hz 轨迹）、`frames.csv`（帧→相机 tick 映射）、`meta.json`
- **编辑**：上排双视口（左=原片+轨迹+取景框+跟随点，右=跟拍视口）；下排时间线 + 参数
- **裁切**：时间线头点「裁切」进入框选模式，拖出保留区间；双击时间线或点「清除裁切」复位
- **轨迹编辑**：左视口头点「轨迹编辑」，在画面上点/拖添加或移动跟随点（≥2 个生效）
- **代理预览**：右视口头点「生成预览」按当前参数渲一版 480p 代理，之后播放走 `<video>`，30fps 顺滑
- **导出**：按当前参数 + 裁切 + 跟随点重新渲染成片

## 运行

```powershell
# 正式壳
cd rust\mc-app
cargo build
.\target\debug\mousecam.exe

# 或以可调试方式启动（开放 CDP 端口，可被脚本驱动/截图）
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=9222"
.\target\debug\mousecam.exe

# HTTP 演示通道（不需要 WebView2）
cd rust\mc-server
cargo run --release
# 浏览器打开 http://127.0.0.1:8765
```

UI 自动取 `captures/` 下最新的 `rec_*` 目录。可用 `MC_CAPTURES` 指定其他位置。

## 打包

```powershell
cd rust\mc-app
$env:TEMP = "$PWD\target\tmp"; $env:TMP = $env:TEMP   # esbuild 清理临时目录时会报 Access denied
node node_modules\@tauri-apps\cli\tauri.js build      # 产出安装包（bundle.targets 决定 msi / nsis）
node node_modules\@tauri-apps\cli\tauri.js build --no-bundle   # 只出 exe
```

注意用 `node .../tauri.js` 而不是 `npx`/`npm run`——这台机器的执行策略会拦 `.ps1`，
`npm.cmd` 同理要用完整路径调。

产物：
- `target/release/mousecam.exe` — 便携版，约 9.5 MB，资源已内嵌
- `target/release/bundle/msi/MouseCam_0.1.0_x64_en-US.msi` — 安装包，约 3.3 MB

> `bundle.targets` 目前设的是 `msi`。`nsis` 也行，但它要额外下载 `nsis_tauri_utils.dll`，
> 而这台机器连不上 `github.com:443`（`objects.githubusercontent.com` 是通的），会卡在最后一步。
> WiX 工具本地已缓存，所以 msi 可以直接出。

## 命令行（无 UI）

```powershell
cd rust\mc-engine
cargo build --release
.\target\release\mc-render.exe --record 6                     # 录 6 秒
.\target\release\mc-render.exe --clip <dir> --out out.mp4     # 重渲染
.\target\release\mc-render.exe --clip <dir> --edit e.mcl      # 按编辑清单重渲染
.\target\release\mc-render.exe --capture-bench 60             # 抓屏基准
```

## 编辑清单 `.mcl`

```
version 1
trim   2.0 6.0        # 保留这些区间，按顺序拼接
trim   12.0 16.0
kf     3.0 600 400    # 手动跟随点（≥2 个才生效，线性插值）
kf     5.0 1900 1000
zoom   1.3
expand 1.6
smooth 70
aspect 2
width  1080
```

优先级：`meta.json` < `edit.mcl` < 命令行参数。

## 实时预览是怎么来的

DXGI 同一个输出只允许**一个** duplication，所以录制中不能另开一路抓屏。因此：

- **空闲**：`mc-api` 起一个独立的预览线程（250Hz 相机 + ~15fps 抓屏 + 裁切），
  把 1080 宽的帧塞进共享槽位，UI 每 110ms 取一次 JPEG。
- **录制中**：预览线程关闭，录制线程自己每 3 帧往同一个槽位写一帧。
- 因此 `preview_frame` 永远能拿到"当前正在录的画面"，录制前后无缝衔接。

## HUD 取景框

`mc-engine/src/hud.rs`：一个 `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_TOPMOST`
的 popup 窗口，品红 colorkey 透明，直接 GDI 绘制边框 + 四角支架 + 尺寸标签，
`SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` 保证它不进录制。

踩坑记录：

- **`SetWindowDisplayAffinity` 必须在 `ShowWindow` 之后调**。在窗口尚未显示时调用会
  返回成功，但亲和性仍是 `WDA_NONE`，HUD 照样被录进去。这个函数不报错，只能靠
  `GetWindowDisplayAffinity` 回读确认（现在是显示后每 tick 重试，直到 `Ok`）。
- **不要在这个窗口里跑消息泵**。`DispatchMessageW` 会在 WM_PAINT 里重入 `paint()`，
  再抢同一把状态锁 → 线程第一次迭代后永久阻塞，窗口停在创建时的 80×80 隐藏状态。
  现在循环只做「读状态 → SetWindowPos → 绘制 → sleep」。
- 尺寸标签必须**紧跟在清屏之后画**。放在边框和角标之后画会看不到（顺序相关的 GDI 状态问题）。
- `COLORREF` 是 `0x00BBGGRR`，不是 RGB；`#4f8cff` 要写成 `0x00FF8C4F`。
- 调试截图时设 `MC_HUD_CAPTURABLE=1` 可临时关掉录制排除，否则截图工具抓不到它。

## 踩过的坑

**1. WebView2 启动即 `拒绝访问 (os error 5)`**

症状：`Failed to setup app: 拒绝访问。(os error 5)`，`%LOCALAPPDATA%\<identifier>\EBWebView` 连目录都不创建。

原因：WebView2 要往 user data folder 写文件，而这里 `%LOCALAPPDATA%` 被策略拒绝（受控文件夹访问一类）。
注意 **`create_dir_all` 成功不代表能写**，必须真的写一个探针文件。

关键细节：**Tauri 2 总会自己设置 `data_directory`**（`tauri/src/webview.rs:562`，指向 app local data dir），
所以 `WEBVIEW2_USER_DATA_FOLDER` 环境变量会被覆盖、设了也没用。必须在 builder 上显式指定：

```rust
WebviewWindowBuilder::new(app, "main", Default::default())
    .data_directory(writable_dir)   // 启动时探测：exe 同级 → LOCALAPPDATA → TEMP
    .build()?;
```

**2. 不要在 Tauri 之前调 `SetProcessDpiAwarenessContext`**

Tauri 在 setup 阶段自己设置 per-monitor-v2；提前设会让它再设一次返回 `ERROR_ACCESS_DENIED`，启动直接 panic。

**3. DDA 结构体字段顺序（析构顺序）**

Rust 按声明顺序析构。`ID3D11Device` 必须**最后**释放，否则 context / texture / duplication
的 `Release()` 会走到已销毁的设备上 → 退出时崩溃。声明顺序：`staging, dup, context, device`。

**4. 相机时钟不能绑在采集时钟上**

实时按帧率 tick（33ms）而离线烘焙按 250Hz（4ms），One Euro 的速度估计强依赖采样间隔，
导致「快移放大」算出不同的视口，导出与录制构图能差 20px。
改成相机跑独立 250Hz 线程，并把每帧用到的 tick 序号写入 `frames.csv`，离线按序号重放。

**5. 截图 WebView2 窗口**

GDI `BitBlt` 拿到全白（DirectComposition 合成，窗口 DC 里没有像素）。
用 CDP：`--remote-debugging-port=9222` + `Page.captureScreenshot`。见 `tools/verify.mjs`。

## 验证

```powershell
node tools\verify.mjs 9222 shots
```

```powershell
node tools\verify.mjs        9222 shots   # 编辑页 7 项
node tools\verify-record.mjs 9222 shots   # 录制闭环 7 项
node tools\verify-edit.mjs   9222 shots   # 裁切 / 关键帧 / 代理 / 导出 9 项
```

## 已知限制

- 原片 `master.mp4` 里**没有光标**：DXGI Desktop Duplication 返回的桌面图不含鼠标，
  光标是在导出/跟拍时单独合成的。要"原片带光标"需要录制时把光标画进 master。
- 播放时左视口走原片 `<video>`，右视口走代理 `<video>`；改了参数后代理会标记为过期，
  右视口退回按需静帧，直到重新点「生成预览」。
- 音频未实现。
