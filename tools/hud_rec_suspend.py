import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8", errors="surrogateescape").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %r" % (c, old[:90]))
    s = s.replace(old, new)

rep("""async function toggleRecord() {""",
"""// Desktop duplication ignores WDA_EXCLUDEFROMCAPTURE, so a visible frame lands
// inside master.mp4 and camera.mp4. Hiding it for the duration of the recording
// is the only reliable way to keep the border out of the picture.
let hudSuspendedForRecording = false;
let hudSuspendHintShown = false;

async function suspendHudForRecording() {
  const btn = $('hudToggle');
  if (!btn || !btn.classList.contains('is-on')) return;
  hudSuspendedForRecording = true;
  btn.classList.remove('is-on');
  try { await invoke('hud_set', { enabled: false }); } catch {}
  if (!hudSuspendHintShown) {
    hudSuspendHintShown = true;
    toast('录制期间已隐藏取景框（否则会录进画面）', 2600);
  }
  // let the overlay process hide before the first frame is grabbed
  await new Promise((r) => setTimeout(r, 140));
}

async function restoreHudAfterRecording() {
  if (!hudSuspendedForRecording) return;
  hudSuspendedForRecording = false;
  const btn = $('hudToggle');
  if (btn) btn.classList.add('is-on');
  try { await invoke('hud_set', { enabled: true }); } catch {}
}

async function toggleRecord() {""")

rep("""      $('recWarn').textContent = '';
      const dir = await invoke('record_start', {""",
"""      $('recWarn').textContent = '';
      await suspendHudForRecording();
      const dir = await invoke('record_start', {""")

rep("""    } catch (e) {
      $('recWarn').textContent = '鍚姩澶辫触: ' + e;
    }""",
"""    } catch (e) {
      await restoreHudAfterRecording();
      $('recWarn').textContent = '启动失败: ' + e;
    }""")

rep("""      const msg = await invoke('record_stop');
      setRecording(false);""",
"""      const msg = await invoke('record_stop');
      setRecording(false);
      await restoreHudAfterRecording();""")
io.open(p, "w", encoding="utf-8", errors="surrogateescape", newline="").write(s)
print("frame is hidden for the duration of a recording")
