import subprocess, sys, glob, os
import numpy as np, cv2
d = sorted(glob.glob(r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\captures\rec_*"), key=os.path.getmtime)[-1]
master = os.path.join(d, "master.mp4")
out = r"E:\RAYS\Desktop\workspace\mousecam\shots\ulw_master.png"
subprocess.run([r"E:\RAYS\Desktop\workspace\mousecam\dist\ffmpeg.exe", "-y", "-v", "error", "-ss", "1.0", "-i", master, "-frames:v", "1", out], check=True)
img = cv2.imread(out)
b, g, r = img[:,:,0].astype(int), img[:,:,1].astype(int), img[:,:,2].astype(int)
mask = ((np.abs(b-255) < 45) & (np.abs(g-140) < 45) & (np.abs(r-79) < 45)).astype(np.uint8)
def longest(row):
    best = cur = 0
    for v in row:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best
h = max(longest(mask[y]) for y in range(0, mask.shape[0], 2))
v = max(longest(mask[:, x]) for x in range(0, mask.shape[1], 2))
print("longest accent run in the recording: h=%d px, v=%d px (frame would be ~1200+)" % (h, v))
