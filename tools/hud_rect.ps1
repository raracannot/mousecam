Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Hud {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int l, t, r, b; }
  public static string Dump() {
    var sb2 = new StringBuilder();
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      var sb = new StringBuilder(128);
      GetClassNameW(h, sb, 128);
      string c = sb.ToString();
      if (!c.StartsWith("MouseCam")) return true;
      RECT r; GetWindowRect(h, out r);
      sb2.Append(c).Append(" visible=").Append(IsWindowVisible(h))
         .Append(" (").Append(r.l).Append(",").Append(r.t).Append(") ")
         .Append(r.r - r.l).Append("x").Append(r.b - r.t).Append("\n");
      return true;
    }, IntPtr.Zero);
    return sb2.ToString();
  }
}
"@ -ErrorAction Stop

[void][Hud]::SetProcessDpiAwarenessContext([IntPtr](-4))
$out = [Hud]::Dump()
if ([string]::IsNullOrWhiteSpace($out)) { "no HUD windows" } else { $out.TrimEnd() }
