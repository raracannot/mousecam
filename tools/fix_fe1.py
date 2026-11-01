import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for: %s" % (c, old[:130]))
    s = s.replace(old, new)

# 1) the crop rect is CENTRED: bake.path holds [cx, cy, w, h], the same thing
#    render.rs turns into x = cx - w*0.5. Using cx as a corner shifted the whole
#    follow view by half a crop.
rep("""  const mon = bake.mon; // [x, y, w, h] in screen pixels
  const k = v.videoWidth / mon[2];
  let sx = (p[0] - mon[0]) * k;
  let sy = (p[1] - mon[1]) * k;
  let sw = p[2] * k;
  let sh = p[3] * k;""",
"""  const mon = bake.mon; // [x, y, w, h] in screen pixels
  // p = [cx, cy, w, h] with the centre, matching render.rs (cx - w * 0.5).
  const kx = v.videoWidth / mon[2];
  const ky = v.videoHeight / mon[3];
  let sw = p[2] * kx;
  let sh = p[3] * ky;
  let sx = (p[0] - mon[0]) * kx - sw / 2;
  let sy = (p[1] - mon[1]) * ky - sh / 2;""")

# 2) scrubbing must move the master video whether or not a proxy exists; only
#    the *crop* view depended on the proxy.
rep("""  const cropFromVideo = state.proxyReady && !state.proxyStale;

  if (state.useVideo && cropFromVideo) {
    seekVideos(state.frame / fps);
    drawLeft();
    drawRight();
    return;
  }""",
"""  const cropFromVideo = state.proxyReady && !state.proxyStale;

  // The master video has to follow the playhead even without a proxy, otherwise
  // clicking the timeline only moves the trace and the right pane.
  if (state.useVideo) seekVideos(state.frame / fps);
  if (state.useVideo && cropFromVideo) {
    drawLeft();
    drawRight();
    return;
  }""")

# 3) a hidden stage reports clientWidth 0; clamping to 1 wrecked the backing
#    store and nothing repainted it when the tab came back.
rep("""  const w = Math.max(1, Math.floor(parent.clientWidth));
  const h = Math.max(1, Math.floor(parent.clientHeight));""",
"""  const pw = Math.floor(parent.clientWidth);
  const ph = Math.floor(parent.clientHeight);
  if (pw < 2 || ph < 2) {
    // The tab is hidden (display:none). Keep the existing backing store rather
    // than resizing it to 1x1, which used to leave a stretched single pixel.
    const ctx = cv.getContext('2d');
    if (!ctx) return { ctx, w: 1, h: 1 };
    ctx.setTransform(window.devicePixelRatio || 1, 0, 0, window.devicePixelRatio || 1, 0, 0);
    return { ctx, w: cv.width / (window.devicePixelRatio || 1), h: cv.height / (window.devicePixelRatio || 1) };
  }
  const w = Math.max(1, pw);
  const h = Math.max(1, ph);""")

# 4) `still` fails routinely while the engine warms up - do not log every one
rep("const QUIET_CALLS = new Set(['preview_frame', 'record_status', 'hud_get', 'hud_get_config', 'media_path']);",
    "const QUIET_CALLS = new Set(['preview_frame', 'record_status', 'hud_get', 'hud_get_config', 'media_path', 'still']);")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("front-end batch 1 applied")
