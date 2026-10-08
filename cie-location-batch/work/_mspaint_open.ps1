param([string]$img)
if (-not $img) { Write-Output 'NO IMG ARG'; exit 1 }
Start-Process mspaint -ArgumentList ('"' + $img + '"')
Start-Sleep -Seconds 3
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W3 {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool repaint);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
'@
[void][W3]::SetProcessDPIAware()
$mp = Get-Process mspaint -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
if (-not $mp) { Write-Output 'MSPAINT NOT RUNNING'; exit 1 }
$script:found = [IntPtr]::Zero
[W3]::EnumWindows({ param($h,$l)
  $wp = [uint32]0
  [void][W3]::GetWindowThreadProcessId($h, [ref]$wp)
  if ($wp -eq $mp.Id) {
    $sb = New-Object System.Text.StringBuilder 512
    [void][W3]::GetWindowText($h,$sb,512)
    if ($sb.ToString().Length -gt 0) { $script:found = $h }
  }
  return $true
}, [IntPtr]::Zero) | Out-Null
if ($script:found -eq [IntPtr]::Zero) { Write-Output ('NO WINDOW for pid ' + $mp.Id); exit 1 }
[void][W3]::MoveWindow($script:found, 820, 0, 2060, 1704, $true)
Write-Output ("MSPAINT_HWND=" + $script:found + " PID=" + $mp.Id)
