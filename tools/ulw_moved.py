import numpy as np, cv2
img = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\ulw_moved.png")
b, g, r = img[:,:,0].astype(int), img[:,:,1].astype(int), img[:,:,2].astype(int)
acc = (np.abs(b-255)<30)&(np.abs(g-140)<30)&(np.abs(r-79)<30)
ys, xs = np.nonzero(acc)
print("accent pixels now  :", int(acc.sum()))
if len(xs): print("frame bbox now     : x %d..%d  y %d..%d" % (xs.min(), xs.max(), ys.min(), ys.max()))
