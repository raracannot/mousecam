import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

anchor = "window.addEventListener('resize', () => {"
assert s.count(anchor) == 1

block = """/* ---------------- draggable splits ---------------- */
// The viewports, the timeline and the params area are laid out by CSS variables,
// so dragging a handle is just a variable write. Sizes persist across runs, which
// matters because the useful split depends on the monitor.
const SPLIT_KEY = 'mc.split';

function applySplits(saved) {
  const stage = $('stageEdit');
  const vps = document.querySelector('.viewports');
  if (!stage || !vps) return;
  if (saved.tl) stage.style.setProperty('--tl-h', saved.tl + 'px');
  if (saved.params) stage.style.setProperty('--params-h', saved.params + 'px');
  if (saved.vp) vps.style.setProperty('--vp-left', saved.vp + '%');
}

function relayout() {
  drawLeft();
  drawRight();
  drawTimeline();
}

function initSplits() {
  const stage = $('stageEdit');
  const vps = document.querySelector('.viewports');
  const timeline = document.querySelector('.timeline');
  const params = document.querySelector('.params');
  if (!stage || !vps || !timeline || !params) return;

  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(SPLIT_KEY) || '{}'); } catch {}
  applySplits(saved);

  const drag = (handle, axis, onDelta, onDone) => {
    if (!handle) return;
    handle.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      handle.setPointerCapture(e.pointerId);
      handle.classList.add('dragging');
      document.body.classList.add('split-drag', axis === 'x' ? 'cols' : 'rows');
      let raf = 0;
      const move = (ev) => {
        if (raf) return;
        raf = requestAnimationFrame(() => {
          raf = 0;
          onDelta(ev);
          relayout();
        });
      };
      const up = () => {
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
        handle.removeEventListener('pointercancel', up);
        handle.classList.remove('dragging');
        document.body.classList.remove('split-drag', 'cols', 'rows');
        onDone();
        relayout();
      };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
      handle.addEventListener('pointercancel', up);
    });
  };

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  // two viewports: share the row width
  drag($('splitVp'), 'x', null, () => {});
  let vpStart = 0, vpW = 1;
  $('splitVp')?.addEventListener('pointerdown', (e) => {
    vpW = vps.getBoundingClientRect().width - 14 || 1;
    vpStart = e.clientX;
    const left = vps.querySelector('.vp').getBoundingClientRect().width;
    const pct0 = (left / vpW) * 100;
    const onMove = (ev) => {
      const pct = clamp(pct0 + ((ev.clientX - vpStart) / vpW) * 100, 22, 78);
      vps.style.setProperty('--vp-left', pct + '%');
    };
    const move = (ev) => onMove(ev);
    const up = () => {
      $('splitVp').removeEventListener('pointermove', move);
      $('splitVp').removeEventListener('pointerup', up);
      saved.vp = parseFloat(vps.style.getPropertyValue('--vp-left')) || 50;
      localStorage.setItem(SPLIT_KEY, JSON.stringify(saved));
    };
    $('splitVp').addEventListener('pointermove', move);
    $('splitVp').addEventListener('pointerup', up);
  });

  // stage rows: dragging the upper handle grows the viewports by shrinking the
  // timeline, the lower one shrinks the params area
  let rowStart = 0, tl0 = 0, params0 = 0, stageH = 0;
  const rowDrag = (id, kind) => {
    const h = $(id);
    if (!h) return;
    h.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      h.setPointerCapture(e.pointerId);
      h.classList.add('dragging');
      document.body.classList.add('split-drag', 'rows');
      rowStart = e.clientY;
      tl0 = timeline.getBoundingClientRect().height;
      params0 = params.getBoundingClientRect().height;
      stageH = stage.getBoundingClientRect().height;
      const move = (ev) => {
        const dy = ev.clientY - rowStart;
        if (kind === 'tl') {
          const v = clamp(tl0 - dy, 56, Math.max(56, stageH - params0 - 160));
          stage.style.setProperty('--tl-h', Math.round(v) + 'px');
        } else {
          const v = clamp(params0 - dy, 84, Math.max(84, stageH - tl0 - 160));
          stage.style.setProperty('--params-h', Math.round(v) + 'px');
        }
        relayout();
      };
      const up = () => {
        h.removeEventListener('pointermove', move);
        h.removeEventListener('pointerup', up);
        h.removeEventListener('pointercancel', up);
        h.classList.remove('dragging');
        document.body.classList.remove('split-drag', 'rows');
        saved.tl = parseInt(stage.style.getPropertyValue('--tl-h')) || undefined;
        saved.params = parseInt(stage.style.getPropertyValue('--params-h')) || undefined;
        localStorage.setItem(SPLIT_KEY, JSON.stringify(saved));
        relayout();
      };
      h.addEventListener('pointermove', move);
      h.addEventListener('pointerup', up);
      h.addEventListener('pointercancel', up);
    });
  };
  rowDrag('splitStageA', 'tl');
  rowDrag('splitStageB', 'params');
}

initSplits();

"""
s = s.replace(anchor, block + anchor)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("split logic added")
