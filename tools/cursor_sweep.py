import numpy as np, cv2, glob, os, re
rows = []
for p in sorted(glob.glob(r"E:\RAYS\Desktop\workspace\mousecam\shots\cf_*.png")):
    t = float(re.search(r"cf_([\d.]+)\.png", p).group(1))
    img = cv2.imread(p)
    g = img.max(axis=2)
    m = g > 60
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        rows.append((t, 0, 0, 0)); continue
    rows.append((t, xs.max()-xs.min()+1, ys.max()-ys.min()+1, int(m.sum())))
print(" time   cursor WxH   pixels")
for t, w, h, n in rows:
    print("%5.1fs   %3dx%-3d   %d" % (t, w, h, n))
