# Keep a standalone KimiCU agent alive for this session's MCP channel.
# Checks the named pipe every ~7s; restarts the agent if the pipe is down.
$exe = 'C:\Users\weo\AppData\Local\KimiCU\kimi-cu.exe'
$log = 'C:/Users/weo/Desktop/api/cie-location-batch/work/_agent_watchdog.log'
while ($true) {
    $alive = $false
    try {
        $pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.', 'kimi-cu-win-weo', [System.IO.Pipes.PipeDirection]::InOut)
        $pipe.Connect(300)
        $alive = $true
        $pipe.Dispose()
    } catch { $alive = $false }
    if (-not $alive) {
        Add-Content -LiteralPath $log -Value "$(Get-Date -Format 'HH:mm:ss') pipe down -> starting agent"
        Start-Process -FilePath $exe -ArgumentList 'agent' -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }
    Start-Sleep -Seconds 7
}
