# Sample kimi-cu process state every 0.5s for ~35s, appending to a log file
$log = "C:/Users/weo/Desktop/api/cie-location-batch/work/_procsample.txt"
Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue
for ($i = 0; $i -lt 70; $i++) {
    $ts = Get-Date -Format "HH:mm:ss.fff"
    $procs = Get-CimInstance Win32_Process -Filter "Name='kimi-cu.exe'" -ErrorAction SilentlyContinue |
        ForEach-Object { "$($_.ProcessId)<-parent:$($_.ParentProcessId) $($_.CommandLine)" }
    $pipeOk = "no"
    try {
        $pipe = New-Object System.IO.Pipes.NamedPipeClientStream(".", "kimi-cu-win-weo", [System.IO.Pipes.PipeDirection]::InOut)
        $pipe.Connect(200)
        $pipeOk = "yes"
        $pipe.Dispose()
    } catch { $pipeOk = "no" }
    Add-Content -LiteralPath $log -Value "$ts pipe=$pipeOk :: $($procs -join ' ;; ')"
    Start-Sleep -Milliseconds 500
}
