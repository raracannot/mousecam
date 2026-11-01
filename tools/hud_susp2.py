import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
lines = io.open(p, encoding="utf-8", errors="surrogateescape").read().split("\n")

# restore on a failed start: the line that prints the start warning
i = next(k for k, l in enumerate(lines) if "recWarn" in l and "textContent" in l)
ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
if "restoreHudAfterRecording" not in lines[i-1]:
    lines[i:i] = [ind + "await restoreHudAfterRecording();"]

# restore after a successful stop
j = next(k for k, l in enumerate(lines) if "await invoke('record_stop')" in l)
k = next(k for k in range(j, j + 6) if lines[k].strip() == "setRecording(false);")
ind2 = lines[k][:len(lines[k]) - len(lines[k].lstrip())]
lines[k+1:k+1] = [ind2 + "await restoreHudAfterRecording();"]
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write("\n".join(lines))
print("restore hooks inserted")
