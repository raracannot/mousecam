param([int]$Steps = 24, [int]$StepMs = 100)
# Drags a foreign application's window around, the way a user would, to check
# that the HUD reacts to a moving cursor without wedging the desktop.
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class FDrag {
  public delegate bool E(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(E cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, int dx, int dy, uint d, UIntPtr e);
  [StructLayout(LayoutKind.Sequential)] public struct R { public int l, t, r, b; }
  public const uint DOWN = 0x0002, UP = 0x0004;
  public static IntPtr Find(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p != pid) return true;
      if (!IsWindowVisible(h)) return true;
      R r; GetWindowRect(h, out r);
      if (r.r - r.l < 200 || r.b - r.t < 100) return true;
      found = h; return false;
    }, IntPtr.Zero);
    return found;
  }
  public static string Rect(IntPtr h) { R r; GetWindowRect(h, out r); return "(" + r.l + "," + r.t + ") " + (r.r-r.l) + "x" + (r.b-r.t); }
}
"@ -ErrorAction Stop

[void][FDrag]::SetProcessDpiAwarenessContext([IntPtr](-4))
$np = Get-Process notepad -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $np) { $np = Start-Process notepad -PassThru; Start-Sleep -Seconds 2 } else { $np = Start-Process notepad -PassThru; Start-Sleep -Seconds 2 }
$h = [FDrag]::Find([uint32]$np.Id)
if ($h -eq [IntPtr]::Zero) { "notepad window not found"; exit 1 }

$r = New-Object FDrag+R
[void][FDrag]::GetWindowRect($h, [ref]$r)
$x = $r.l + 120
$y = $r.t + 14
"notepad: $([FDrag]::Rect($h))  grabbing ($x,$y)"

[void][FDrag]::SetCursorPos($x, $y)
Start-Sleep -Milliseconds 250
[FDrag]::mouse_event([FDrag]::DOWN, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 150

# sweep the window across the screen and back
for ($i = 0; $i -lt $Steps; $i++) {
    $t = $i / [double]$Steps * 2 * [math]::PI
    $nx = 400 + [int](760 * [math]::Cos($t))
    $ny = 380 + [int](280 * [math]::Sin($t))
    [void][FDrag]::SetCursorPos($nx, $ny)
    Start-Sleep -Milliseconds $StepMs
}
[FDrag]::mouse_event([FDrag]::UP, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 400
"notepad after drag: $([FDrag]::Rect($h))"
Get-Process notepad -ErrorAction SilentlyContinue | Stop-Process -Force
