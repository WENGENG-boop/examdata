$out = 'C:\Users\weo\Desktop\api\cie-location-batch\work\_chrome_watch.log'
$deadline = (Get-Date).AddMinutes(9.5)
$seen = $false
while ((Get-Date) -lt $deadline) {
  $ts = Get-Date -Format 'HH:mm:ss.fff'
  $procs = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -match '_chrome_verify' }
  if ($procs) {
    $seen = $true
    $ids = ($procs | ForEach-Object { $_.ProcessId }) -join ','
    Add-Content -Path $out -Value "$ts ALIVE $ids"
  } elseif ($seen) {
    Add-Content -Path $out -Value "$ts DEAD"
    break
  }
  Start-Sleep -Seconds 2
}
Add-Content -Path $out -Value "$(Get-Date -Format 'HH:mm:ss.fff') WATCH_END seen=$seen"
