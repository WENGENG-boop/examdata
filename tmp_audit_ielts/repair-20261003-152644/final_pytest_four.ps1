# Final four-file verification (spec section 5, item 3): offline + live
# Pure ASCII only (PS 5.1 mis-reads UTF-8-no-BOM with non-ASCII as GBK).
Set-Location C:/Users/weo/Desktop/api/examdata
$env:PYTHONIOENCODING='utf-8'
$env:EXAMDATA_DATABASE_URL='sqlite:///:memory:'
Remove-Item Env:TMPDIR -ErrorAction SilentlyContinue
Remove-Item Env:EXAMDATA_TEST_LIVE -ErrorAction SilentlyContinue

$files = @(
  'tests/test_api_ielts.py',
  'tests/test_ielts_concurrency.py',
  'tests/test_api_unified.py',
  'tests/test_api_contracts.py'
)

Write-Output "=== OFFLINE RUN ==="
./.venv/Scripts/python.exe -m pytest @files -v *> "C:/Users/weo/Desktop/api/tmp_audit_ielts/repair-20261003-152644/evidence/final-pytest-four-offline.txt"
Write-Output "OFFLINE_EXIT=$LASTEXITCODE"

Write-Output "=== LIVE RUN ==="
$env:EXAMDATA_TEST_LIVE='1'
./.venv/Scripts/python.exe -m pytest @files -v *> "C:/Users/weo/Desktop/api/tmp_audit_ielts/repair-20261003-152644/evidence/final-pytest-four-live.txt"
Write-Output "LIVE_EXIT=$LASTEXITCODE"
Remove-Item Env:EXAMDATA_TEST_LIVE -ErrorAction SilentlyContinue
Write-Output "DONE"
