import numpy as np, cv2
img = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\blackblock.png")
h, w = img.shape[:2]
# "black" = near-uniform dark
dark = (img.max(axis=2) < 24).astype(np.uint8)
print("image:", img.shape, "| dark pixels:", int(dark.sum()), "(%.1f%%)" % (100*dark.sum()/(h*w)))
# largest dark rectangle bounds
ys, xs = np.nonzero(dark)
if len(xs):
    print("dark bbox: x %d..%d  y %d..%d" % (xs.min(), xs.max(), ys.min(), ys.max()))
# row/column coverage of the dark area
rows = dark.sum(axis=1); cols = dark.sum(axis=0)
big_rows = np.nonzero(rows > w*0.5)[0]
big_cols = np.nonzero(cols > h*0.5)[0]
if len(big_rows): print("rows >50%% dark: %d..%d" % (big_rows.min(), big_rows.max()))
if len(big_cols): print("cols >50%% dark: %d..%d" % (big_cols.min(), big_cols.max()))
