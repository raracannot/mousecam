param([string]$Out = "E:\RAYS\Desktop\workspace\mousecam\shots")
# Verifies the colour key: the area inside the HUD window but away from its
# frame must show the desktop, not an opaque fill.
Add-Type -TypeDefinition @"
using System; using System.Drawing; using System.Runtime.InteropServices;
public class G {
  [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr v);
  public static void Grab(int x,int y,int w,int h,string p){
    SetProcessDpiAwarenessContext(new IntPtr(-4));
    var b=new Bitmap(w,h); var g=Graphics.FromImage(b);
    g.CopyFromScreen(x,y,0,0,new Size(w,h)); g.Dispose();
    b.Save(p, System.Drawing.Imaging.ImageFormat.Png); b.Dispose(); }
}
"@ -ReferencedAssemblies System.Drawing -ErrorAction Stop

# HUD rect comes from the helper script
$rect = (& powershell -NoProfile -ExecutionPolicy Bypass -File "E:\RAYS\Desktop\workspace\mousecam\tools\hud_rect.ps1") -join " "
if ($rect -notmatch '\((-?\d+),(-?\d+)\)\s+(\d+)x(\d+)') { "no HUD window: $rect"; exit 1 }
$x = [int]$Matches[1]; $y = [int]$Matches[2]; $w = [int]$Matches[3]; $h = [int]$Matches[4]
"HUD at $x,$y ${w}x${h}"

[G]::Grab(($x + 40), ($y + 40), 120, 90, "$Out\a_hud_on.png")
Start-Sleep -Milliseconds 300
"captured with the HUD visible"
