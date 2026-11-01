import numpy as np, cv2

img = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\97_master_frame.png")
b, g, r = img[:,:,0].astype(int), img[:,:,1].astype(int), img[:,:,2].astype(int)
mask = ((np.abs(b-255) < 45) & (np.abs(g-140) < 45) & (np.abs(r-79) < 45)).astype(np.uint8)

def longest_run(row):
    best = cur = 0
    for v in row:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best

h = max(longest_run(mask[y]) for y in range(0, mask.shape[0], 2))
v = max(longest_run(mask[:, x]) for x in range(0, mask.shape[1], 2))
print("longest horizontal accent run:", h, "px")
print("longest vertical   accent run:", v, "px")
print("HUD frame would produce runs of ~1200-1300 px")
