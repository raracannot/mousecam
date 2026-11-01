param([int]$ProcId)
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Mv {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
  [DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int l, t, r, b; }
  public static string Rect(IntPtr h) {
    RECT r; GetWindowRect(h, out r);
    return "(" + r.l + "," + r.t + ") " + (r.r - r.l) + "x" + (r.b - r.t);
  }
  public static IntPtr FindMain(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p != pid) return true;
      var sb = new StringBuilder(128); GetClassNameW(h, sb, 128);
      if (sb.ToString().StartsWith("MouseCam")) return true;       // our HUD windows
      if (!IsWindowVisible(h)) return true;
      RECT r; GetWindowRect(h, out r);
      if (r.r - r.l < 300) return true;
      found = h;
      return false;
    }, IntPtr.Zero);
    return found;
  }
}
"@ -ErrorAction Stop

[void][Mv]::SetProcessDpiAwarenessContext([IntPtr](-4))
$h = [Mv]::FindMain($ProcId)
if ($h -eq [IntPtr]::Zero) { "window not found for pid $ProcId"; exit 1 }
"before : $([Mv]::Rect($h))  hung=$([Mv]::IsHungAppWindow($h))"

[void][Mv]::SetWindowPos($h, [IntPtr]::Zero, 2560, 100, 1280, 860, 0x0004)
Start-Sleep -Milliseconds 1200
"moved  : $([Mv]::Rect($h))  hung=$([Mv]::IsHungAppWindow($h))"

for ($i = 0; $i -lt 8; $i++) {
  [void][Mv]::SetWindowPos($h, [IntPtr]::Zero, 2600 + $i * 10, 120 + $i * 8, 1280, 860, 0x0004)
  Start-Sleep -Milliseconds 220
  if ([Mv]::IsHungAppWindow($h)) { "HUNG at step $i : $([Mv]::Rect($h))"; break }
}
"after  : $([Mv]::Rect($h))  hung=$([Mv]::IsHungAppWindow($h))"
