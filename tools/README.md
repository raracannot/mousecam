# tools/

开发期的自动化脚本。它们通过 **Chrome DevTools Protocol** 驱动界面（而不是截图比对），因此能直接读到真实的 DOM 状态与引擎返回。

## 准备

1. 用调试端口启动应用：

   ```bat
   set WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222
   start rust\mc-app\target\debug\mousecam.exe
   ```

2. 脚本默认连接 `http://127.0.0.1:9222`。用 `MC_SETTINGS` 把配置指向测试用的 ini，避免污染你自己的捕获目录：

   ```bat
   set MC_SETTINGS=%CD%\rust\mc-engine\settings.ini
   set MC_LOG=%CD%\rust\mc-engine\test-run.log
   ```

## mc.mjs —— 一条命令查一件事

大多数时候不需要手写 CDP 代码，直接用封装好的命令行：

```bat
node tools\mc.mjs state                  # 应用与录制器的实时状态（含相机、帧耗时、磁盘）
node tools\mc.mjs record 5               # 录 5 秒，结束后自动出体检报告
node tools\mc.mjs probe                  # 最新素材的体检报告
node tools\mc.mjs probe <素材目录>        # 指定素材
node tools\mc.mjs clips                  # 列出素材
node tools\mc.mjs still <素材> <帧> <输出.png>
node tools\mc.mjs bake <素材>             # 逐帧取景矩形
```

## 合成模式：不碰你的桌面

```bat
node tools\mc.mjs record 5 --synthetic
```

这个模式里，采集**不读桌面**，画面是引擎自己画的（网格 + 逐帧移动的品红方块 + 白边框），光标走一条固定的脚本轨迹（弧线，含快慢段，用来触发"快速移动放大"）。

好处是录制测试可以**和你并行**：你的鼠标不会被抢，屏幕上你在做什么都不会进到测试素材里。产物、帧率、补帧、音画同步、跟拍解算全部照常，所以测的还是真代码路径。

只在 debug 构建生效——`record_start` 会检查 `debug_assertions`，发行版里这个开关不存在。

## 素材体检（probe）

一次录制好不好，光看画面看不出来。体检读的是素材已经写下的东西（`meta.json`、`frames.csv`、`track.csv`、音频 WAV），所以**旧素材也能复查**：

```
✓ 无异常   ...\rec_20261104_081106
  帧 112 · 补帧 0 · 刻度倒退 0 · 开头静止 0ms
  时长 3.70s · 音频 3.87s · 贴边 0 帧 · 丢帧 0

✗ 有问题   ...\rec_20261104_071239
  帧 129 · 补帧 9 · 刻度倒退 0 · 开头静止 200ms
  时长 4.28s · 音频 4.37s · 贴边 0 帧 · 丢帧 0
  · 开头约 200 ms 画面是静止的（6 帧没有推进取景）
```

界面里也会在每次录制结束后自动跑一遍，有问题就直接提示，不用等回放才发现。

## 跟拍调参：量化工具

`smooth-bench.py` 用两条**模拟人手**的轨迹（`trackgen.py` 生成）给跟拍打分：

- **原地画圈**：70px 半径 1.6Hz，半径/频率随机漂移，叠加 8–12Hz 手抖——用来测"视口会不会跟着手一起晃"
- **普通移动**：随机目标点、缓入缓出、5% 过冲、停顿——用来测跟随是否跟手

指标里刻意把**慢漂移**和**晃动**分开：`波动 rms` 是相机相对自身 0.5s 均值的偏移，这才是"晃悠"；总行程会把缓慢平移也算进去。

```bat
python tools\trackgen.py        # 生成两条轨迹到 target\track-*
python tools\smooth-bench.py    # 对当前参数打表
```

## 推送：`push-via-api.mjs`

有些网络下 `github.com:443` 能建 TCP 连接、却在 HTTPS 握手后被重置，`git push` 会卡到超时，而 `api.github.com` 一直是通的。这个工具就绕开 git 传输层，直接用 GitHub REST API 按 git 对象模型推送（blob → tree → commit → 更新 ref）。

```bat
node tools\push-via-api.mjs                  :: 预演，只列出要推的提交
node tools\push-via-api.mjs --yes            :: 真正推送
node tools\push-via-api.mjs --yes --tag v0.3.0   :: 顺带推一个 tag
```

**SHA 什么时候不变**：重建 commit 用的是原始 author / committer。GitHub 会把提交时间统一成 UTC 表示，所以**在 UTC 时区创建的提交**推完 SHA 完全一致；在别的时区创建的提交，同一时刻会写成 `+0000`，字节不同、SHA 也就变了。

后一种情况工具会自动把本地分支移到服务端的新提交上——两者树对象完全相同，工作区文件不会有任何变化——所以推完 `git status` 依然是干净的。不想让它动本地就加 `--no-adopt`，工具会只打印命令。

Token 取 `GH_TOKEN` / `GITHUB_TOKEN` 环境变量，否则从 `git credential` 里读 `github.com` 的凭据；不落盘。

安全边界：只做快进推送。远端有本地没有的提交时直接拒绝，不会强推。

## 回归套件

每个套件都应当**在全新的应用实例上跑**，连着跑会互相污染状态（裁切区间、关键帧会残留）。

| 脚本 | 覆盖内容 |
|---|---|
| `verify.mjs` | 素材载入、时间线定位、参数重算、两个视口都有画面 |
| `verify-timeline.mjs` | 时间线点击定位、缩放跨度、帧号一致性 |
| `verify-edit.mjs` | 拖拽建裁切、跟随关键帧、代理生成、播放推进、导出弹窗与时长 |
| `verify-recpreview.mjs` | 录制页实时预览出图、参数即时影响、录制中预览继续工作 |
| `verify-loop.mjs` | 自动回放开关、尾帧行为 |
| `verify-cursor.mjs` | 旧素材的预览光标插值、边界、关键帧与缩放映射（纯 node） |
| `verify-speed.mjs` | 变速区间的重叠、夹紧、序列化与单段删除（纯 node） |
| `verify-playback.mjs` | 预览时钟与导出时间轴一致（变速 + 裁切映射，纯 node） |
| `verify-stillcache.mjs` | 静帧缓存：按源帧归档、单次解码、字节预算、过期结果不写入（纯 node） |

```bat
node tools\verify.mjs 9222 shots
```

最后一个参数是截图输出目录。

## 录制与诊断

| 脚本 | 用途 |
|---|---|
| `open-rec.mjs` | 切到录制页 |
| `hudrec.mjs start\|stop` | 开始/停止一次录制 |
| `rec8.mjs` | 录 8 秒并等待落盘 |
| `check-alive.mjs` | 判断界面是否响应（比 `Responding` 属性可靠） |
| `hud_rect.ps1` | 打印取景框窗口的位置与尺寸 |
| `hud_in_rec.py` | 检查成片里是否混入了取景框边框（量最长连续强调色像素） |
| `enum_win.py` / `enum_win_aware.py` | 枚举窗口（后者按物理像素测量，避免 DPI 虚拟化误差） |
| `shot.mjs` / `shot_rec.mjs` / `shot_settings.mjs` | 截图 |

## 压力与基准

| 脚本 | 用途 |
|---|---|
| `bench-record.ps1` | 录制的 CPU 占用 |
| `bench-preview.ps1` / `bench-preview2.mjs` | 预览链路耗时 |
| `drag_win.ps1` / `drag_foreign.ps1` / `move_win.ps1` | 拖动窗口（曾经是取景框卡死的复现路径） |

`portable_readme.txt` 是便携版 `说明.txt` 的源文本。
