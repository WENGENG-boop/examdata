param([string]$List, [string]$Out)
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null

# 图像装载一律走 .NET 读字节 + AsRandomAccessStream：
# 从 Python 启动 PowerShell 时，WinRT 的 StorageFile.GetFileFromPathAsync 会抛
# UnauthorizedAccessException(0x80070005)，InMemoryRandomAccessStream 会抛
# WINCODEC_ERR_COMPONENTNOTFOUND(0x88982F50)，只有这条路能稳定解码。
$engine = $null
foreach ($tag in @('en-US','en-GB','en')) {
    try {
        $lang = New-Object Windows.Globalization.Language $tag
        $e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
        if ($e) { $engine = $e; break }
    } catch { }
}
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if (-not $engine) { Write-Output "NO_OCR_ENGINE"; exit 2 }

$sb = New-Object System.Text.StringBuilder
$paths = [System.IO.File]::ReadAllLines($List, (New-Object System.Text.UTF8Encoding $false))
foreach ($p in $paths) {
    $p = $p.Trim()
    if ($p -eq '') { continue }
    $ms = $null; $ras = $null
    try {
        $bytes = [System.IO.File]::ReadAllBytes($p)
        $ms = New-Object System.IO.MemoryStream
        $ms.Write($bytes, 0, $bytes.Length)
        $ms.Position = 0
        $ras = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($ms)
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ras)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $W = [int]$decoder.PixelWidth; $H = [int]$decoder.PixelHeight
        $sb0 = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $bitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($sb0, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)
        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    } catch {
        $ex = $_.Exception
        $msg = $ex.GetType().Name + ': ' + $ex.Message
        $inner = $ex.InnerException
        $depth = 0
        while ($inner -and $depth -lt 4) {
            $msg += ' <- ' + $inner.GetType().Name + ': ' + $inner.Message
            $inner = $inner.InnerException
            $depth++
        }
        try {
            $msg += ' @L' + $_.InvocationInfo.ScriptLineNumber + ':' + ($_.InvocationInfo.Line -replace '\s+', ' ').Trim()
        } catch { }
        [void]$sb.AppendLine("$p`tERR`t$msg")
        if ($ras) { try { $ras.Dispose() } catch { } }
        if ($ms) { try { $ms.Dispose() } catch { } }
        continue
    }
    [void]$sb.AppendLine("$p`tSIZE`t$W`t$H")
    foreach ($line in $result.Lines) {
        if ($line.Words.Count -eq 0) { continue }
        $words = @(); foreach ($w in $line.Words) { $words += $w.Text }
        $minx = [double]::MaxValue; $miny = [double]::MaxValue; $maxx = -1.0; $maxy = -1.0
        foreach ($w in $line.Words) {
            $r = $w.BoundingRect
            $rx = [double]$r.X; $ry = [double]$r.Y; $rw = [double]$r.Width; $rh = [double]$r.Height
            if ($rx -lt $minx) { $minx = $rx }
            if ($ry -lt $miny) { $miny = $ry }
            if (($rx + $rw) -gt $maxx) { $maxx = $rx + $rw }
            if (($ry + $rh) -gt $maxy) { $maxy = $ry + $rh }
        }
        $s = "$p`tLINE`t{0:F1}`t{1:F1}`t{2:F1}`t{3:F1}`t{4}" -f $minx, $miny, $maxx, $maxy, ($words -join ' ')
        [void]$sb.AppendLine($s)
    }
    if ($ras) { try { $ras.Dispose() } catch { } }
    if ($ms) { try { $ms.Dispose() } catch { } }
}
[System.IO.File]::WriteAllText($Out, $sb.ToString(), (New-Object System.Text.UTF8Encoding $false))
Write-Output ("IMAGES=" + $paths.Count)
