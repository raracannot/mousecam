import numpy as np, cv2
for name in ("cursor_slow", "cursor_fast"):
    img = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\%s.png" % name)
    g = img.max(axis=2)
    mask = g > 60
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        print(name, "no cursor found"); continue
    w = xs.max() - xs.min() + 1
    h = ys.max() - ys.min() + 1
    print("%-12s cursor bbox %dx%d  at (%d,%d)  pixels=%d" % (name, w, h, xs.min(), ys.min(), len(xs)))
