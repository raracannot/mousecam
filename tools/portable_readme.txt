MouseCam 0.1.0  （便携版）
================================

跟随鼠标的屏幕录制与取景工具。录屏时会同时生成三份输出：
  · master.mp4   完整原片（保留全屏，供二次裁切）
  · camera.mp4   跟拍成片（自动裁切、跟随光标的视口，轨迹已平滑）
  · track.csv    鼠标轨迹（坐标 + 时间，250Hz）
  另外还有 frames.csv（帧→相机映射）和 meta.json（录制参数）。


运行
----
直接双击 mousecam.exe。无需安装，但需要同目录下的 ffmpeg.exe（已附带）。

系统要求：
  · Windows 10 2004 及以上（64 位）
  · WebView2 运行时 —— Windows 11 自带；若提示缺失，
    安装微软的 "Microsoft Edge WebView2 Runtime" 即可。


快捷键
------
  F9  或  Ctrl+Alt+R      开始 / 停止录制（全局有效，不必切回窗口）

  在录制页还可以用鼠标点左上角圆钮开始、方形按钮停止。


输出文件夹（可自定义）
----------------------
  默认：系统「视频」库下的 MouseCam 文件夹
        （例如 C:\Users\你的用户名\Videos\MouseCam；
          如果视频库被重定向到别的盘，就跟着走那个盘）
        该位置不可写时，自动回退到 %LOCALAPPDATA%\MouseCam\captures

  点标题栏右上角的齿轮 →「设置」可以改成任意文件夹，
  编辑页的素材列表也跟着这个文件夹走。

  每次录制生成一个 rec_年月日_时分秒 子文件夹。

  其它覆盖方式：环境变量 MC_CAPTURES 指定输出目录，
                MC_SETTINGS 指定设置文件位置（便携场景有用）。


两个页面
--------
  【编辑】  打开已有素材，拖动时间线裁切、加跟随关键帧，
            调整跟拍参数后导出（支持 MP4 / H.265 / WebM / GIF / ProRes）。
  【录制】  实时看到跟拍视口的画面，边调参数边看效果；
            可开关屏幕上的取景框，可用硬件编码降低 CPU 占用。


设置文件
--------
  %LOCALAPPDATA%\MouseCam\settings.ini
  内容是若干 key=value 行，可以直接用文本编辑器改：
     captures=输出文件夹      （留空 = 用默认位置）
     hw=1 / 0                 （录制时默认硬件编码）
     hud=1 / 0                （录制时默认显示取景框）


日志（排查问题先看这里）
------------------------
  位置：mousecam.exe 同目录的 mousecam.log
  内容按行记录，带毫秒时间戳和级别：

    2026-11-01 12:11:05.578  INFO   [app       ] monitor 0: 2560x1440 at 0,0 primary=true
    2026-11-01 12:11:11.032  ERROR  [panic     ] deliberate test panic at main.rs:208 (thread tokio-rt-worker)
    2026-11-01 12:11:09.833  ERROR  [ui        ] JS 异常: Uncaught Error: ... @ :1:20

  会记录：启动上下文（版本 / 屏幕 / 显卡相关路径 / ffmpeg / 输出目录）、
          每次开始与结束录制、导出、所有 panic（含后台线程）、
          前端 JS 异常与未处理的 Promise 拒绝、以及每一个失败的命令调用。

  设置里可以打开「记录详细日志」写 DEBUG 级别；文件超过 4 MB 自动轮转为
  mousecam.log.1，不会无限增长。


排查
----
  · 启动后在 exe 同目录生成 mousecam.log，记录了启动过程和 WebView2 配置。
  · 提示「找不到 ffmpeg.exe」：确认 ffmpeg.exe 与 mousecam.exe 在同一目录，
    或设置环境变量 MC_FFMPEG 指向 ffmpeg.exe 的完整路径。
  · 录制的画面全黑：通常是显卡驱动不支持 DXGI 桌面复制，
    程序会回退到 GDI 抓屏，兼容性更好但帧率略低。
