$py = 'C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe'
$out = 'C:/Users/weo/Desktop/api/cie-location-batch/work/static-8792.out.log'
$err = 'C:/Users/weo/Desktop/api/cie-location-batch/work/static-8792.err.log'
$p = Start-Process -FilePath $py -ArgumentList '-m','http.server','8792','--bind','127.0.0.1','--directory','C:/Users/weo/Desktop/api/cie-location-batch' -WindowStyle Hidden -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
"PID=$($p.Id)" | Out-File -Encoding utf8 'C:/Users/weo/Desktop/api/cie-location-batch/work/static-8792.pid.txt'
Write-Output "Started PID=$($p.Id)"
