import cv2
img = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\95_hud_live.png")
print("shot:", img.shape)
x, y, w, h = 340, 621, 1288, 728
pad = 40
crop = img[max(0, y-pad):y+h+pad, max(0, x-pad):x+w+pad]
cv2.imwrite(r"E:\RAYS\Desktop\workspace\mousecam\shots\96_hud_crop.png", crop)
print("crop saved:", crop.shape)
