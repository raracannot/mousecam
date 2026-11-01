import io
p = r"E:\RAYS\Desktop\workspace\mousecam\tools\portable_readme.txt"
s = io.open(p, encoding="utf-8").read()
old = """排查
----"""
new = """日志（排查问题先看这里）
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
----"""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("readme updated")
