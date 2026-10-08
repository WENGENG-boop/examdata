# Legacy launcher for the examdata API on 127.0.0.1:8000 (kept for compatibility).
# Unified with restart_serve_8000.ps1 on 2026-10-03: same DATA_DIR, same proven DATABASE_URL,
# same writable TMP/TEMP. Previously this script pointed EXAMDATA_DATABASE_URL at
# .pytest_cache/callable-api/examdata.db, which contains 0 questions/0 boards - a launcher
# using it would serve empty search results. See CIE_REPAIR_REPORT.md.
# NOTE: keep this file pure ASCII - PowerShell 5.1 misparses UTF-8 no-BOM files with
# non-ASCII comments and silently drops the following lines (verified 2026-10-03).
$env:EXAMDATA_DATA_DIR = 'C:/Users/weo/Desktop/api/examdata/.pytest_cache/callable-api'
$env:EXAMDATA_DATABASE_URL = 'sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db'
$env:EXAMDATA_MAX_RETRIES = '1'
$tmp = 'C:\Users\weo\Desktop\api\examdata\.data\tmp'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$env:TMP = $tmp
$env:TEMP = $tmp
Remove-Item Env:TMPDIR -ErrorAction SilentlyContinue
$exe = 'C:/Users/weo/Desktop/api/examdata/.venv/Scripts/examdata.exe'
$out = 'C:/Users/weo/Desktop/api/cie-location-batch/work/serve8000.out.log'
$err = 'C:/Users/weo/Desktop/api/cie-location-batch/work/serve8000.err.log'
$p = Start-Process -FilePath $exe -ArgumentList 'serve','--host','127.0.0.1','--port','8000' -WorkingDirectory 'C:\Users\weo\Desktop\api\examdata' -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
"PID=$($p.Id)" | Out-File -Encoding utf8 'C:/Users/weo/Desktop/api/cie-location-batch/work/serve8000.pid.txt'
Write-Output "Started PID=$($p.Id)"
