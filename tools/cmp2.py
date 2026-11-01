import numpy as np, cv2
a = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\k_on.png")
b = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\k_off.png")
print("shapes:", a.shape, b.shape)
d = np.abs(a.astype(int) - b.astype(int))
print("mean |diff| :", round(float(d.mean()), 2))
print("max  |diff| :", int(d.max()))
print("HUD interior pixel (on) :", a[50, 70].tolist())
print("same pixel (off)        :", b[50, 70].tolist())
