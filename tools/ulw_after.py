import numpy as np, cv2
img = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\ulw_after_drag.png")
dark = (img.max(axis=2) < 24)
print("dark fraction after drags: %.1f%%" % (100*dark.sum()/dark.size))
b, g, r = img[:,:,0].astype(int), img[:,:,1].astype(int), img[:,:,2].astype(int)
acc = (np.abs(b-255)<30)&(np.abs(g-140)<30)&(np.abs(r-79)<30)
print("accent pixels after drags:", int(acc.sum()))
