import os, json, glob
root = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\captures"
clips = sorted(glob.glob(os.path.join(root, "rec_*")), key=os.path.getmtime, reverse=True)[:6]
for c in clips:
    m = os.path.join(c, "master.mp4")
    meta = os.path.join(c, "meta.json")
    size = os.path.getsize(m) if os.path.exists(m) else -1
    frames = ""
    if os.path.exists(meta):
        try:
            d = json.load(open(meta))
            frames = "frames=%s dur=%s" % (d.get("frames"), d.get("duration"))
        except Exception as e:
            frames = "meta unreadable"
    print("%-28s master=%-10s %s" % (os.path.basename(c), size, frames))
