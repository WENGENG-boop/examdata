# Manual cleanup of work/sheets/probe42* dirs (paper 0472/2025/Jun/42 visual aids).
# Validates each absolute path stays under work/sheets/ and is not a reparse point,
# then deletes one file at a time with Remove-Item -LiteralPath. No recursion into
# BATCH_ROOT; only these four explicitly named directories.
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\weo\Desktop\api\cie-location-batch\work\sheets'
$allowedPrefix = (Resolve-Path -LiteralPath $root).Path + '\'
$dirs = @('probe42', 'probe42b', 'probe42c', 'probe42d') | ForEach-Object { Join-Path $root $_ }

$deleted = New-Object System.Collections.Generic.List[string]
$refused = New-Object System.Collections.Generic.List[string]
$freed = 0

foreach ($dir in $dirs) {
    if (-not (Test-Path -LiteralPath $dir)) { continue }
    $dirFull = (Resolve-Path -LiteralPath $dir).Path
    if (-not $dirFull.StartsWith($allowedPrefix)) { $refused.Add("outside: $dirFull"); continue }
    $dirItem = Get-Item -LiteralPath $dirFull -Force
    if ($dirItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { $refused.Add("reparse dir: $dirFull"); continue }

    $files = Get-ChildItem -LiteralPath $dirFull -File -Recurse -Force
    foreach ($f in $files) {
        $full = $f.FullName
        if (-not $full.StartsWith($allowedPrefix)) { $refused.Add("outside: $full"); continue }
        if ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) { $refused.Add("reparse: $full"); continue }
        $size = $f.Length
        Remove-Item -LiteralPath $full -Force
        if (Test-Path -LiteralPath $full) { $refused.Add("still present: $full"); continue }
        $deleted.Add($full)
        $freed += $size
    }

    # remove now-empty subdirs deepest-first, then the dir itself (never -Recurse)
    $subdirs = Get-ChildItem -LiteralPath $dirFull -Directory -Recurse -Force | Sort-Object { $_.FullName.Length } -Descending
    foreach ($sd in $subdirs) {
        if ((Get-ChildItem -LiteralPath $sd.FullName -Force | Measure-Object).Count -eq 0) {
            Remove-Item -LiteralPath $sd.FullName
        }
    }
    if ((Get-ChildItem -LiteralPath $dirFull -Force | Measure-Object).Count -eq 0) {
        Remove-Item -LiteralPath $dirFull
    }
}

Write-Output ("deleted=" + $deleted.Count + " freed=" + $freed + " refused=" + $refused.Count)
$deleted | ForEach-Object { Write-Output ("DEL " + $_) }
$refused | ForEach-Object { Write-Output ("REF " + $_) }
