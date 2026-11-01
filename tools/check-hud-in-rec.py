import subprocess, glob
import numpy as np, cv2

clip = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\captures\rec_20261101_130141"
master = clip + r"\master.mp4"
out = r"E:\RAYS\Desktop\workspace\mousecam\shots\97_master_frame.png"
subprocess.run([r"E:\RAYS\Desktop\workspace\mousecam\dist\ffmpeg.exe", "-y", "-v", "error",
                "-ss", "1.0", "-i", master, "-frames:v", "1", out], check=True)
img = cv2.imread(out)
b, g, r = img[:,:,0].astype(int), img[:,:,1].astype(int), img[:,:,2].astype(int)
# HUD accent #4f8cff -> BGR(255,140,79); allow h264 softening
mask = (np.abs(b-255) < 45) & (np.abs(g-140) < 45) & (np.abs(r-79) < 45)
ys, xs = np.nonzero(mask)
print("frame:", img.shape, "| accent-ish pixels:", int(mask.sum()))
if len(xs):
    print("bbox: x %d..%d  y %d..%d" % (xs.min(), xs.max(), ys.min(), ys.max()))
