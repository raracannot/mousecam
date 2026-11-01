import io

# ---------------- HTML ----------------
p = r"rust\mc-app\ui\index.html"
s = io.open(p, encoding="utf-8").read()

old = """    <div class="winbtns" data-tauri-drag-region>
      <button class="wb" id="wbMin" title="最小化">"""
new = """    <div class="winbtns" data-tauri-drag-region>
      <button class="wb" id="wbSettings" title="设置">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <circle cx="6" cy="6" r="1.9" stroke="currentColor" stroke-width="1.1"/>
          <path d="M6 1.1v1.5M6 9.4v1.5M1.1 6h1.5M9.4 6h1.5M2.55 2.55l1.05 1.05M8.4 8.4l1.05 1.05M9.45 2.55L8.4 3.6M3.6 8.4L2.55 9.45"
                stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>
        </svg>
      </button>
      <button class="wb" id="wbMin" title="最小化">"""
assert s.count(old) == 1
s = s.replace(old, new)

anchor = '<script src="app.js"></script>'
modal = """
  <!-- ─── app settings ─── -->
  <div class="modal is-hidden" id="settingsModal">
    <div class="modal-card modal-wide">
      <div class="modal-head">设置</div>
      <div class="modal-body">
        <label class="frow frow-col"><span>输出文件夹</span>
          <input type="text" id="setCaptures" class="txt-input" placeholder="留空则使用默认位置" />
        </label>
        <div class="fhint" id="setCapturesHint">录制的素材保存在这里，编辑页也从这里读取。</div>
        <div class="frow frow-actions">
          <button class="head-btn" id="setOpen">打开文件夹</button>
          <button class="head-btn" id="setDefault">恢复默认位置</button>
        </div>
        <label class="frow frow-check"><input type="checkbox" id="setHw" /> 录制时默认使用硬件编码（NVENC）</label>
        <label class="frow frow-check"><input type="checkbox" id="setHud" /> 录制时默认显示屏幕取景框</label>
        <div class="fhint" id="setAbout"></div>
      </div>
      <div class="modal-foot">
        <button class="head-btn" id="setCancel">取消</button>
        <button class="head-btn is-on" id="setSave">保存</button>
      </div>
    </div>
  </div>

"""
assert s.count(anchor) == 1
s = s.replace(anchor, modal + "  " + anchor)
io.open(p, "w", encoding="utf-8", newline="").write(s)

# ---------------- CSS ----------------
p = r"rust\mc-app\ui\app.css"
s = io.open(p, encoding="utf-8").read()
s += """
.modal-wide { width: 470px; }
.frow-col {
  grid-template-columns: 1fr;
  gap: 6px;
}
.txt-input {
  width: 100%;
  box-sizing: border-box;
  height: 28px;
  padding: 0 9px;
  font: inherit;
  font-size: 12px;
  color: var(--text);
  background: var(--surface-3, #151b25);
  border: 1px solid var(--line);
  border-radius: 6px;
}
.txt-input:focus { outline: none; border-color: var(--accent); }
.frow-actions { grid-template-columns: 1fr 1fr; gap: 8px; }
.frow-check {
  grid-template-columns: auto 1fr;
  gap: 8px;
  color: var(--text-2, #b6c0cf);
}
.frow-check input { accent-color: var(--accent); }
#wbSettings { margin-right: 4px; }
"""
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("settings markup + styles")
