import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for:\n%s" % (c, old[:150]))
    s = s.replace(old, new)

rep("""function drawRight() {
  const cv = $('cropCanvas');
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  // the proxy video already shows the cropped result
  if (state.proxyReady && !state.proxyStale) return;
  if (!state.cropImg) return;""",
"""// Cut the current camera rect out of the playing master video. Drawing a frame
// that is already decoded is free, so the follow view keeps up with playback -
// the still path costs ~270 ms per frame and always trails behind.
function drawCropFromVideo() {
  const v = $('viewVideo');
  if (!state.useVideo || v.readyState < 2 || !v.videoWidth) return false;
  const bake = state.bake;
  if (!bake || !bake.path || !bake.mon) return false;
  const p = bake.path[state.frame];
  if (!p) return false;

  const mon = bake.mon; // [x, y, w, h] in screen pixels
  const k = v.videoWidth / mon[2];
  let sx = (p[0] - mon[0]) * k;
  let sy = (p[1] - mon[1]) * k;
  let sw = p[2] * k;
  let sh = p[3] * k;
  sx = Math.max(0, Math.min(v.videoWidth - 2, sx));
  sy = Math.max(0, Math.min(v.videoHeight - 2, sy));
  sw = Math.max(2, Math.min(v.videoWidth - sx, sw));
  sh = Math.max(2, Math.min(v.videoHeight - sy, sh));

  const cv = $('cropCanvas');
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  const box = fitInside(w, h, sw, sh);
  ctx.drawImage(v, sx, sy, sw, sh, box.x, box.y, box.w, box.h);
  ctx.strokeStyle = 'rgba(255,255,255,.06)';
  ctx.lineWidth = 1;
  ctx.strokeRect(box.x + .5, box.y + .5, box.w - 1, box.h - 1);
  return true;
}

function drawRight() {
  const cv = $('cropCanvas');
  const { ctx, w, h } = sizeCanvas(cv);
  ctx.clearRect(0, 0, w, h);
  // the proxy video already shows the cropped result
  if (state.proxyReady && !state.proxyStale) return;
  if (drawCropFromVideo()) return;
  if (!state.cropImg) return;""")

# keep the follow view moving during playback even without a proxy
rep("""    state.frame = Math.max(0, Math.min(last, Math.round(v.currentTime * fps)));
    drawTimeline();
    drawLeft();""",
"""    state.frame = Math.max(0, Math.min(last, Math.round(v.currentTime * fps)));
    drawTimeline();
    drawLeft();
    if (!(state.proxyReady && !state.proxyStale)) drawRight();""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("follow view now crops the playing video")
