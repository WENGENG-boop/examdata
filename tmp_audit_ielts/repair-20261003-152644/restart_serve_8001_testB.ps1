# Diagnostic script B (8001 isolated verification only; does not touch the official service)
# Hardened variant: explicit DATABASE_URL + explicit writable TMP/TEMP (examdata/.data/tmp,
# verified python-writable). Blueprint for the new 8000 launcher.
# NOTE: pure ASCII only - PowerShell 5.1 misparses UTF-8 no-BOM files with non-ASCII comments
#       and silently drops following lines (verified 2026-10-03).
$env:EXAMDATA_DATA_DIR = 'C:/Users/weo/Desktop/api/examdata/.pytest_cache/callable-api'
$env:EXAMDATA_DATABASE_URL = 'sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db'
$env:TMP = 'C:\Users\weo\Desktop\api\examdata\.data\tmp'
$env:TEMP = 'C:\Users\weo\Desktop\api\examdata\.data\tmp'
Remove-Item Env:TMPDIR -ErrorAction SilentlyContinue
$p = Start-Process -FilePath 'C:\Users\weo\Desktop\api\examdata\.venv\Scripts\examdata.exe' `
  -ArgumentList 'serve','--host','127.0.0.1','--port','8001' `
  -WorkingDirectory 'C:\Users\weo\Desktop\api\examdata' `
  -WindowStyle Hidden `
  -RedirectStandardOutput 'C:\Users\weo\Desktop\api\tmp_audit_ielts\repair-20261003-152644\evidence\serve-8001B.out.log' `
  -RedirectStandardError 'C:\Users\weo\Desktop\api\tmp_audit_ielts\repair-20261003-152644\evidence\serve-8001B.err.log' `
  -PassThru
Write-Output "STARTED_PID=$($p.Id)"
