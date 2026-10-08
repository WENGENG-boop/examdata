# Unified launcher for the examdata API on 127.0.0.1:8000.
# Fix (2026-10-03): explicit DATABASE_URL (proven DB, 42789 questions), explicit writable
# TMP/TEMP, absolute WorkingDirectory, TMPDIR cleared.
# Why: previously the DB path depended on the caller's CWD (SQLAlchemy resolves relative
# sqlite URLs against the process CWD) and TMP pointed at a directory the Python process
# cannot write; SQLite temp files then failed with "unable to open database file" on large
# ORDER BY queries. See CIE_REPAIR_REPORT.md for the diagnosis.
# NOTE: keep this file pure ASCII - PowerShell 5.1 misparses UTF-8 no-BOM files with
# non-ASCII comments and silently drops the following lines (verified 2026-10-03).
$env:EXAMDATA_DATA_DIR = 'C:/Users/weo/Desktop/api/examdata/.pytest_cache/callable-api'
$env:EXAMDATA_DATABASE_URL = 'sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db'
$tmp = 'C:\Users\weo\Desktop\api\examdata\.data\tmp'
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$env:TMP = $tmp
$env:TEMP = $tmp
Remove-Item Env:TMPDIR -ErrorAction SilentlyContinue
$p = Start-Process -FilePath 'C:\Users\weo\Desktop\api\examdata\.venv\Scripts\examdata.exe' `
  -ArgumentList 'serve','--host','127.0.0.1','--port','8000' `
  -WorkingDirectory 'C:\Users\weo\Desktop\api\examdata' `
  -WindowStyle Hidden `
  -RedirectStandardOutput 'C:\Users\weo\Desktop\api\cie-location-batch\work\serve-8000-20261003.out.log' `
  -RedirectStandardError 'C:\Users\weo\Desktop\api\cie-location-batch\work\serve-8000-20261003.err.log' `
  -PassThru
$p.Id | Out-File -Encoding ascii 'C:\Users\weo\Desktop\api\cie-location-batch\work\serve-8000.pid.txt'
Write-Output "STARTED_PID=$($p.Id)"
