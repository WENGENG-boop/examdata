param([string]$Path, [string]$Out)
$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null

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

try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $W = [double]$decoder.PixelWidth; $H = [double]$decoder.PixelHeight
    $sb0 = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $bitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($sb0, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
} catch {
    Write-Output ("ERR: " + $_.Exception.Message); exit 3
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("SIZE`t$W`t$H")
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
    $s = '{0:F1}`t{1:F1}`t{2:F1}`t{3:F1}`t{4}' -f $minx, $miny, $maxx, $maxy, ($words -join ' ')
    [void]$sb.AppendLine($s)
}
[System.IO.File]::WriteAllText($Out, $sb.ToString(), (New-Object System.Text.UTF8Encoding $false))
Write-Output ("LINES=" + $result.Lines.Count)
