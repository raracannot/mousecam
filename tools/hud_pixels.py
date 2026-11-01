import cv2, numpy as np
img = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\95_hud_live.png")
# accent #4f8cff -> BGR (255,140,79)
b, g, r = img[:,:,0].astype(int), img[:,:,1].astype(int), img[:,:,2].astype(int)
mask = (np.abs(b-255) < 30) & (np.abs(g-140) < 30) & (np.abs(r-79) < 30)
print("accent pixels on screen:", int(mask.sum()))
ys, xs = np.nonzero(mask)
if len(xs):
    print("accent bbox: x %d..%d  y %d..%d" % (xs.min(), xs.max(), ys.min(), ys.max()))
    print("HUD window is at 340,621 1288x728")
    inside = ((xs >= 340) & (xs <= 340+1288) & (ys >= 621) & (ys <= 621+728)).sum()
    print("accent pixels inside the HUD rect:", int(inside))
