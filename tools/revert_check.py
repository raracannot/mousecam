import numpy as np, cv2
img = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\revert_check.png")
dark = (img.max(axis=2) < 24)
print("dark fraction: %.1f%%  (was 100%% with the slab)" % (100*dark.sum()/dark.size))
b, g, r = img[:,:,0].astype(int), img[:,:,1].astype(int), img[:,:,2].astype(int)
acc = (np.abs(b-255)<30)&(np.abs(g-140)<30)&(np.abs(r-79)<30)
print("accent pixels (frame):", int(acc.sum()))
