param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [int]$Seconds = 5,
    [string]$Tag = "run"
)
# Measures what a recording actually costs: wall time, frames, and the CPU time
# of the process while it records.
$ErrorActionPreference = "Continue"
$env:MC_SETTINGS = "E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\settings.ini"
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=9222"

Get-Process mousecam, msedgewebview2 -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 800
Start-Process -FilePath $Exe | Out-Null
for ($i = 0; $i -lt 80; $i++) {
    try { $r = Invoke-WebRequest "http://127.0.0.1:9222/json/version" -UseBasicParsing -TimeoutSec 1; if ($r.StatusCode -eq 200) { break } } catch {}
    Start-Sleep -Milliseconds 250
}
Start-Sleep -Seconds 4

$probe = @'
const base = "http://127.0.0.1:9222";
const ts = await (await fetch(`${base}/json`)).json();
const p = ts.find(t => t.type === "page" && !t.url.startsWith("devtools://"));
const ws = new WebSocket(p.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m.result); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p={}) => new Promise(r => { const i=++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method:m, params:p})); });
const ev = async (e) => { const r = await send("Runtime.evaluate", {expression:e, returnByValue:true, awaitPromise:true}); return r.result?.value ?? ('EXC ' + (r.exceptionDetails?.text||'')); };
const cmd = process.argv[2];
if (cmd === "start") {
  await ev(`document.querySelector('.tab[data-tab="record"]').click()`);
  await new Promise(r => setTimeout(r, 2500));
  console.log(await ev(`window.__TAURI__.core.invoke('record_start', { edit: '', monitor: 0, hw: false }).then(r=>'OK '+r).catch(e=>'ERR '+e)`));
} else {
  console.log(await ev(`window.__TAURI__.core.invoke('record_stop').then(r=>'OK '+r).catch(e=>'ERR '+e)`));
}
ws.close();
'@
$probePath = "E:\RAYS\Desktop\workspace\mousecam\tools\rec-probe.mjs"
Set-Content -Path $probePath -Value $probe -Encoding utf8

$startLine = node $probePath start
$proc = Get-Process mousecam | Select-Object -First 1
$cpu0 = $proc.TotalProcessorTime
$t0 = Get-Date
Start-Sleep -Seconds $Seconds
$proc.Refresh()
$cpu1 = $proc.TotalProcessorTime
$t1 = Get-Date
$stopLine = node $probePath stop
Start-Sleep -Milliseconds 1200

$wall = ($t1 - $t0).TotalSeconds
$cpu = ($cpu1 - $cpu0).TotalSeconds
$pct = if ($wall -gt 0) { [math]::Round($cpu / $wall * 100, 1) } else { 0 }
$clip = ($stopLine -replace '^OK ', '') -split '  ' | Select-Object -First 1

"$Tag | cpu=${pct}%  cpu_s=$([math]::Round($cpu,2))  wall=$([math]::Round($wall,2))s"
"$Tag | $stopLine"
if (Test-Path $clip) {
    $meta = Get-Content (Join-Path $clip "meta.json") -Raw -ErrorAction SilentlyContinue
    if ($meta) { "$Tag | meta: $($meta.Trim())" }
}
Get-Process mousecam, msedgewebview2 -ErrorAction SilentlyContinue | Stop-Process -Force
