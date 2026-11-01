const base = "http://127.0.0.1:9222";
try {
  const ts = await (await fetch(`${base}/json`, { signal: AbortSignal.timeout(3000) })).json();
  const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
  const ws = new WebSocket(p.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; setTimeout(() => rej(new Error("ws timeout")), 3000); });
  let id = 0; const pend = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
  const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); setTimeout(() => { if (pend.has(i)) { pend.delete(i); r(null); } }, 4000); });
  const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r ? (r.result?.value ?? "null") : "TIMEOUT"; };
  console.log("page alive:", await ev(`1+1`));
  console.log("recPreview.src length:", await ev(`(document.getElementById('recPreview').src || '').length`));
  console.log("preview_frame result:", await ev(`window.__TAURI__.core.invoke('preview_frame').then(u => 'OK len=' + u.length).catch(e => 'ERR ' + e)`));
  console.log("record_status:", await ev(`window.__TAURI__.core.invoke('record_status').then(r => JSON.stringify(r)).catch(e => 'ERR ' + e)`));
  console.log("recPreviewTimer state:", await ev(`JSON.stringify({on: window.__mc.recPreviewOn, recording: window.__mc.recording})`));
  ws.close();
} catch (e) {
  console.log("CDP UNREACHABLE:", e.message);
}
