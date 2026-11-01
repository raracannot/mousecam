import json, subprocess
import numpy as np, cv2

info = json.load(open(r"E:\RAYS\Desktop\workspace\mousecam\shots\99_crop_info.json"))
cx, cy, w, h = info["path"]
mx, my, mw, mh = info["mon"]
frame, fps = info["frame"], info["fps"]
canvas = cv2.imread(r"E:\RAYS\Desktop\workspace\mousecam\shots\99_crop_canvas.png")
H, W = canvas.shape[:2]
print("canvas:", canvas.shape, "| centre=(%.0f,%.0f) size=%.0fx%.0f" % (cx, cy, w, h))

master = info["dir"] + r"\master.mp4"
ref = r"E:\RAYS\Desktop\workspace\mousecam\shots\99_master_ref.png"
subprocess.run([r"E:\RAYS\Desktop\workspace\mousecam\dist\ffmpeg.exe", "-y", "-v", "error",
                "-ss", "%.3f" % (frame / fps), "-i", master, "-frames:v", "1", ref], check=True)
full = cv2.imread(ref)
print("master frame:", full.shape)

def crop_at(corner_x, corner_y):
    x0 = int(round(corner_x)); y0 = int(round(corner_y))
    x1 = min(full.shape[1], x0 + int(round(w))); y1 = min(full.shape[0], y0 + int(round(h)))
    x0 = max(0, x0); y0 = max(0, y0)
    piece = full[y0:y1, x0:x1]
    return cv2.resize(piece, (W, H), interpolation=cv2.INTER_AREA)

centre = crop_at(cx - w / 2 - mx, cy - h / 2 - my)   # what the fix should do
corner = crop_at(cx - mx, cy - my)                   # what the bug did

for name, cand in (("centre (fixed)", centre), ("corner (old bug)", corner)):
    diff = np.abs(cand.astype(int) - canvas.astype(int)).mean()
    corr = np.corrcoef(cand.astype(np.float32).ravel(), canvas.astype(np.float32).ravel())[0, 1]
    print("%-18s mean|diff|=%.2f  correlation=%.4f" % (name, diff, corr))
