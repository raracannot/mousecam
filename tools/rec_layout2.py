import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

def rep(old, new, n=1):
    global s
    c = s.count(old)
    if c != n:
        raise SystemExit("matched %d for %s" % (c, old[:110]))
    s = s.replace(old, new)

# 1) persist and restore the recorder params height too
rep("""  if (saved.tl) stage.style.setProperty('--tl-h', saved.tl + 'px');""",
"""  const rec = $('stageRecord');
  if (rec && saved.recParams) rec.style.setProperty('--rec-params-h', saved.recParams + 'px');
  if (saved.tl) stage.style.setProperty('--tl-h', saved.tl + 'px');""")

# 2) the recorder page gets the same draggable params panel
rep("""  rowDrag('splitStageA', 'tl');
  rowDrag('splitStageB', 'params');""",
"""  rowDrag('splitStageA', 'tl');
  rowDrag('splitStageB', 'params');

  // recorder page: preview / control bar / params, the params panel is resizable
  const recStage = $('stageRecord');
  const recParams = recStage && recStage.querySelector('.params');
  const recHandle = $('splitRecParams');
  if (recStage && recParams && recHandle) {
    recHandle.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      try { recHandle.setPointerCapture(e.pointerId); } catch {}
      recHandle.classList.add('dragging');
      document.body.classList.add('split-drag', 'rows');
      const startY = e.clientY;
      const h0 = recParams.getBoundingClientRect().height;
      const stageH = recStage.getBoundingClientRect().height;
      const move = (ev) => {
        const v = clamp(h0 - (ev.clientY - startY), 90, Math.max(90, stageH - 170));
        recStage.style.setProperty('--rec-params-h', Math.round(v) + 'px');
      };
      const up = () => {
        recHandle.removeEventListener('pointermove', move);
        recHandle.removeEventListener('pointerup', up);
        recHandle.classList.remove('dragging');
        document.body.classList.remove('split-drag', 'rows');
        saved.recParams = parseInt(recStage.style.getPropertyValue('--rec-params-h')) || undefined;
        localStorage.setItem(SPLIT_KEY, JSON.stringify(saved));
      };
      recHandle.addEventListener('pointermove', move);
      recHandle.addEventListener('pointerup', up);
    });
  }""")

# 3) leaving the recorder page closes the on-screen frame
rep("""function leaveRecordTab() {
  state.recPreviewOn = false;
  clearTimeout(recPreviewTimer);
  if (!state.recording) invoke('preview_stop').catch(() => {});
}""",
"""function leaveRecordTab() {
  state.recPreviewOn = false;
  clearTimeout(recPreviewTimer);
  if (!state.recording) invoke('preview_stop').catch(() => {});
  // The frame only describes what the recorder page is previewing, so it has no
  // meaning on the editor. Leaving it on would leave a border floating over an
  // unrelated screen.
  if ($('hudToggle').classList.contains('is-on')) {
    $('hudToggle').classList.remove('is-on');
    state.hudOn = false;
    invoke('hud_set', { enabled: false }).catch(() => {});
  }
}""")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("recorder split + auto-close on leaving the tab")
