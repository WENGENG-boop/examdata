# Trace process tree for kimi-cu processes
$procs = Get-CimInstance Win32_Process -Filter "Name='kimi-cu.exe' or Name='Kimi Code.exe' or Name='kimi.exe'"
foreach ($p in $procs) {
    $parent = $procs | Where-Object { $_.ProcessId -eq $p.ParentProcessId }
    $parentName = if ($parent) { "$($parent.Name) ($($parent.ProcessId))" } else { "PID $($p.ParentProcessId)" }
    Write-Output ("PID {0}  {1}  started {2}  parent: {3}" -f $p.ProcessId, $p.Name, $p.CreationDate, $parentName)
}
