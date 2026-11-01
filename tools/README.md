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

## 回归套件

每个套件都应当**在全新的应用实例上跑**，连着跑会互相污染状态（裁切区间、关键帧会残留）。

| 脚本 | 覆盖内容 |
|---|---|
| `verify.mjs` | 素材载入、时间线定位、参数重算、两个视口都有画面 |
| `verify-timeline.mjs` | 时间线点击定位、缩放跨度、帧号一致性 |
| `verify-edit.mjs` | 拖拽建裁切、跟随关键帧、代理生成、播放推进、导出弹窗与时长 |
| `verify-recpreview.mjs` | 录制页实时预览出图、参数即时影响、录制中预览继续工作 |
| `verify-loop.mjs` | 自动回放开关、尾帧行为 |

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
