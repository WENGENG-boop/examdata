Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WE2 {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
'@
[void][WE2]::SetProcessDPIAware()
[WE2]::EnumWindows({ param($h,$l)
  if ([WE2]::IsWindowVisible($h)) {
    $sb = New-Object System.Text.StringBuilder 512
    [void][WE2]::GetWindowText($h,$sb,512)
    $t = $sb.ToString()
    if ($t.Length -gt 0) {
      $wp = [uint32]0
      [void][WE2]::GetWindowThreadProcessId($h, [ref]$wp)
      $pn = (Get-Process -Id $wp -ErrorAction SilentlyContinue).ProcessName
      Write-Output ("HWND=$h PID=$wp PROC=$pn TITLE=$t")
    }
  }
  return $true
}, [IntPtr]::Zero) | Out-Null
