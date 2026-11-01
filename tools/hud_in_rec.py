import subprocess, os, glob
import numpy as np, cv2

ff = r"E:\RAYS\Desktop\workspace\mousecam\dist\ffmpeg.exe"
clip = sorted(glob.glob(r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\captures\rec_*"), key=os.path.getmtime)[-1]
print("clip:", os.path.basename(clip))

def longest_run(mask):
    best = 0
    for row in mask:
        cur = 0
        for v in row:
            cur = cur + 1 if v else 0
            if cur > best:
                best = cur
    return best

for name in ("master.mp4", "camera.mp4"):
    path = os.path.join(clip, name)
    out = os.path.join(r"E:\RAYS\Desktop\workspace\mousecam\shots", "hudcheck_" + name + ".png")
    subprocess.run([ff, "-y", "-v", "error", "-ss", "2.0", "-i", path, "-frames:v", "1", out], check=True)
    img = cv2.imread(out)
    b, g, r = img[:,:,0].astype(int), img[:,:,1].astype(int), img[:,:,2].astype(int)
    # the overlay accent is #4f8cff
    acc = ((np.abs(b - 255) < 40) & (np.abs(g - 140) < 40) & (np.abs(r - 79) < 40)).astype(np.uint8)
    h = longest_run(acc)
    v = longest_run(acc.T)
    print("%-11s size=%dx%d accent=%d  longest run h=%d v=%d" % (name, img.shape[1], img.shape[0], acc.sum(), h, v))
