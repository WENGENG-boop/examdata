# Diagnostic script A (8001 isolated verification only; does not touch the official service)
# Replicates restart_serve_8000.ps1 environment (DATA_DIR + CWD only); port and log paths changed.
# Purpose: verify that a restart with current code (which has temp_store=MEMORY) fixes the search 500.
# NOTE: pure ASCII only - PowerShell 5.1 misparses UTF-8 no-BOM files with non-ASCII comments
#       and silently drops following lines (verified 2026-10-03).
$env:EXAMDATA_DATA_DIR = 'C:/Users/weo/Desktop/api/examdata/.pytest_cache/callable-api'
Remove-Item Env:EXAMDATA_DATABASE_URL -ErrorAction SilentlyContinue
# Replicate PID 22612's original environment (TMP/TEMP pointing at the python-unwritable user temp dir)
$env:TMP = 'C:\Users\weo\AppData\Local\Temp'
$env:TEMP = 'C:\Users\weo\AppData\Local\Temp'
Remove-Item Env:TMPDIR -ErrorAction SilentlyContinue
$p = Start-Process -FilePath 'C:\Users\weo\Desktop\api\examdata\.venv\Scripts\examdata.exe' `
  -ArgumentList 'serve','--host','127.0.0.1','--port','8001' `
  -WorkingDirectory 'C:\Users\weo\Desktop\api\examdata' `
  -WindowStyle Hidden `
  -RedirectStandardOutput 'C:\Users\weo\Desktop\api\tmp_audit_ielts\repair-20261003-152644\evidence\serve-8001A.out.log' `
  -RedirectStandardError 'C:\Users\weo\Desktop\api\tmp_audit_ielts\repair-20261003-152644\evidence\serve-8001A.err.log' `
  -PassThru
Write-Output "STARTED_PID=$($p.Id)"
