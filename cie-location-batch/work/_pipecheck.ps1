$ErrorActionPreference = 'Continue'
Write-Output "=== kimi pipes ==="
[System.IO.Directory]::GetFiles("\\.\pipe\") | Where-Object { $_ -match 'kimi' } | ForEach-Object { Write-Output $_ }

Write-Output "=== connect test ==="
$pipe = New-Object System.IO.Pipes.NamedPipeClientStream(".", "kimi-cu-win-weo", [System.IO.Pipes.PipeDirection]::InOut)
try {
    $pipe.Connect(3000)
    Write-Output "CONNECTED: pipe is alive"
} catch {
    Write-Output ("FAILED: " + $_.Exception.Message)
} finally {
    $pipe.Dispose()
}

Write-Output "=== agent cmdline ==="
Get-CimInstance Win32_Process -Filter "ProcessId=54652" | Select-Object ProcessId,CommandLine | Format-List
