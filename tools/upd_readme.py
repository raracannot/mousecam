import io
p = r"E:\RAYS\Desktop\workspace\mousecam\tools\portable_readme.txt"
s = io.open(p, encoding="utf-8").read()
old = """录制文件保存在哪
----------------
  文档\\..\\Videos\\MouseCam        （即「视频」库下的 MouseCam 文件夹）
  例如 C:\\Users\\你的用户名\\Videos\\MouseCam

  每次录制一个 rec_年月日_时分秒 子文件夹。
  想在别处保存，可以设置环境变量 MC_CAPTURES 指向任意目录。"""
new = """输出文件夹（可自定义）
----------------------
  默认：系统「视频」库下的 MouseCam 文件夹
        （例如 C:\\Users\\你的用户名\\Videos\\MouseCam；
          如果视频库被重定向到别的盘，就跟着走那个盘）
        该位置不可写时，自动回退到 %LOCALAPPDATA%\\MouseCam\\captures

  点标题栏右上角的齿轮 →「设置」可以改成任意文件夹，
  编辑页的素材列表也跟着这个文件夹走。

  每次录制生成一个 rec_年月日_时分秒 子文件夹。

  其它覆盖方式：环境变量 MC_CAPTURES 指定输出目录，
                MC_SETTINGS 指定设置文件位置（便携场景有用）。"""
assert s.count(old) == 1
s = s.replace(old, new)

old2 = """排查
----"""
new2 = """设置文件
--------
  %LOCALAPPDATA%\\MouseCam\\settings.ini
  内容是若干 key=value 行，可以直接用文本编辑器改：
     captures=输出文件夹      （留空 = 用默认位置）
     hw=1 / 0                 （录制时默认硬件编码）
     hud=1 / 0                （录制时默认显示取景框）


排查
----"""
assert s.count(old2) == 1
s = s.replace(old2, new2)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("readme updated")
