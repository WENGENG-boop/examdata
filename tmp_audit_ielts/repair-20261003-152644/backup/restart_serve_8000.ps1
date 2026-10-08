$env:EXAMDATA_DATA_DIR = 'C:/Users/weo/Desktop/api/examdata/.pytest_cache/callable-api'
$p = Start-Process -FilePath 'C:\Users\weo\Desktop\api\examdata\.venv\Scripts\examdata.exe' `
  -ArgumentList 'serve','--host','127.0.0.1','--port','8000' `
  -WorkingDirectory 'C:\Users\weo\Desktop\api\examdata' `
  -WindowStyle Hidden `
  -RedirectStandardOutput 'C:\Users\weo\Desktop\api\cie-location-batch\work\serve-8000.out.log' `
  -RedirectStandardError 'C:\Users\weo\Desktop\api\cie-location-batch\work\serve-8000.err.log' `
  -PassThru
Write-Output "STARTED_PID=$($p.Id)"
