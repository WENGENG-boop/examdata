# Test connection to the KimiCU agent pipe
$pipeName = 'kimi-cu-win-weo'
$connected = $false
try {
    $pipe = New-Object System.IO.Pipes.NamedPipeClientStream('.', $pipeName, [System.IO.Pipes.PipeDirection]::InOut)
    $pipe.Connect(3000)
    $connected = $true
    Write-Output "CONNECTED: pipe is alive"
    $pipe.Dispose()
} catch {
    Write-Output ("CONNECT FAILED: " + $_.Exception.Message)
}
# Also list which pipe names exist now
Write-Output "--- pipes matching kimi ---"
[System.IO.Directory]::GetFiles('\\.\pipe\') | Where-Object { $_ -like '*kimi*' }
