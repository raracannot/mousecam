param([int]$ProcId)
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Drag {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
  [DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, int dx, int dy, uint d, UIntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int l, t, r, b; }
  public const uint DOWN = 0x0002, UP = 0x0004;
  public static IntPtr FindMain(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p != pid) return true;
      var sb = new StringBuilder(128); GetClassNameW(h, sb, 128);
      if (sb.ToString().StartsWith("MouseCam")) return true;
      if (!IsWindowVisible(h)) return true;
      RECT r; GetWindowRect(h, out r);
      if (r.r - r.l < 300) return true;
      found = h; return false;
    }, IntPtr.Zero);
    return found;
  }
  public static string Rect(IntPtr h) { RECT r; GetWindowRect(h, out r); return "(" + r.l + "," + r.t + ") " + (r.r-r.l) + "x" + (r.b-r.t); }
}
"@ -ErrorAction Stop

[void][Drag]::SetProcessDpiAwarenessContext([IntPtr](-4))
$h = [Drag]::FindMain($ProcId)
if ($h -eq [IntPtr]::Zero) { "window not found"; exit 1 }

$r = New-Object Drag+RECT
[void][Drag]::GetWindowRect($h, [ref]$r)
$startX = $r.l + 40
$startY = $r.t + 18          # title bar
"window: $([Drag]::Rect($h))  drag from ($startX,$startY)"

[void][Drag]::SetCursorPos($startX, $startY)
Start-Sleep -Milliseconds 300
[Drag]::mouse_event([Drag]::DOWN, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 200

# drag across to the secondary monitor, in small steps
$targetX = 3200
for ($x = $startX; $x -le $targetX; $x += 60) {
  [void][Drag]::SetCursorPos($x, $startY)
  Start-Sleep -Milliseconds 40
  if ([Drag]::IsHungAppWindow($h)) { "HUNG while dragging at x=$x"; break }
}
Start-Sleep -Milliseconds 300
[Drag]::mouse_event([Drag]::UP, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 800
"final: $([Drag]::Rect($h))  hung=$([Drag]::IsHungAppWindow($h))"
