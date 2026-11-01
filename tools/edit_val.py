import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-app\ui\app.js"
s = io.open(p, encoding="utf-8").read()

old = """      paint();
      inp.oninput = () => {
        state.edit[p.key] = Number(inp.value);
        paint();
        onParamChanged();
      };
      row.appendChild(inp);
      row.appendChild(val);"""
new = """      paint();
      inp.oninput = () => {
        state.edit[p.key] = Number(inp.value);
        paint();
        onParamChanged();
      };

      // Double-click the number to type an exact value. The slider cannot be
      // precise enough by hand, and the parameter ranges are wide (0.5-3.0 zoom,
      // 200-6000 px/s), so typing is the only practical way to hit a value.
      val.title = '双击输入数值';
      val.ondblclick = () => {
        if (val.dataset.editing) return;
        val.dataset.editing = '1';
        const before = Number(inp.value);
        const ed = document.createElement('input');
        ed.type = 'text';
        ed.className = 'row-val-edit';
        ed.value = String(Number(before.toFixed(6)));
        ed.inputMode = 'decimal';
        val.textContent = '';
        val.appendChild(ed);
        ed.focus();
        ed.select();

        let done = false;
        const finish = (commit) => {
          if (done) return;
          done = true;
          delete val.dataset.editing;
          // Detach first: replacing the node can fire blur, which would
          // otherwise re-enter here and commit twice.
          ed.onblur = null;
          val.textContent = '';
          if (commit) {
            const raw = ed.value.replace(',', '.').replace(/[^0-9.\\-]/g, '');
            const n = parseFloat(raw);
            if (Number.isFinite(n)) {
              inp.value = String(Math.min(p.max, Math.max(p.min, n)));
              state.edit[p.key] = Number(inp.value);
              onParamChanged();
            }
          }
          paint();
        };
        ed.onkeydown = (e) => {
          // The window-wide handler watches for F9/F10; typing "3" must not
          // start a recording, and Escape must not clear the selection.
          e.stopPropagation();
          if (e.key === 'Enter') {
            e.preventDefault();
            finish(true);
          } else if (e.key === 'Escape') {
            e.preventDefault();
            finish(false);
          }
        };
        ed.onblur = () => finish(true);
      };
      row.appendChild(inp);
      row.appendChild(val);"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("double-click editing added")
