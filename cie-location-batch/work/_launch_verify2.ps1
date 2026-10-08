$profileDir = 'C:\Users\weo\Desktop\api\cie-location-batch\work\_chrome_verify'
$url = $args[0]
if (-not $url) { $url = 'http://127.0.0.1:8792/work/sheets/0472-2026-Jun-41-qp-regions-stack-3.html' }
Start-Process 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList "--user-data-dir=$profileDir",'--no-first-run','--no-default-browser-check','--remote-debugging-port=9223','--remote-allow-origins=*','--disable-features=CalculateNativeWinOcclusion','--window-position=410,0','--window-size=1030,850',$url
Start-Sleep -Seconds 6
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W2 {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool repaint);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
'@
[void][W2]::SetProcessDPIAware()
$script:found = [IntPtr]::Zero
[W2]::EnumWindows({ param($h,$l)
  $sb = New-Object System.Text.StringBuilder 512
  [void][W2]::GetWindowText($h,$sb,512)
  $t = $sb.ToString()
  if ($t -match '0472-2026-Jun-41') { $script:found = $h }
  return $true
}, [IntPtr]::Zero) | Out-Null
if ($script:found -eq [IntPtr]::Zero) { Write-Output 'WINDOW NOT FOUND'; exit 1 }
[void][W2]::MoveWindow($script:found, 820, 0, 2060, 1704, $true)
Write-Output ("HWND=" + $script:found)
