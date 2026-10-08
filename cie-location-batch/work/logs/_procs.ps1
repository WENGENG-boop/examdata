Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object { "$($_.ProcessId): $($_.CommandLine)" }
