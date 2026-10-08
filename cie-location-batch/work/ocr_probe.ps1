param([string]$Path)
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

$engine = $null
foreach ($tag in @('en-US','en-GB','en')) {
    try {
        $lang = New-Object Windows.Globalization.Language $tag
        $e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
        if ($e) { $engine = $e; break }
    } catch { }
}
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
Write-Output ("ENGINE=" + $engine.RecognizerLanguage.LanguageTag)

# 方案 A: System.IO.MemoryStream -> AsRandomAccessStream
try {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $ms = New-Object System.IO.MemoryStream
    $ms.Write($bytes, 0, $bytes.Length)
    $ms.Position = 0
    $ras = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($ms)
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ras)) ([Windows.Graphics.Imaging.BitmapDecoder])
    Write-Output ("A_OK " + $decoder.PixelWidth + "x" + $decoder.PixelHeight)
    $sb0 = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $bmp = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($sb0, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)
    $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
    Write-Output ("A_LINES=" + $res.Lines.Count)
    foreach ($l in $res.Lines) { if ($l.Words.Count -gt 0) { Write-Output ("  A| " + $l.Text) } }
} catch {
    Write-Output ("A_FAIL " + $_.Exception.InnerException.InnerException.Message)
}

# 方案 B: InMemoryRandomAccessStream + DataWriter + explicit PNG content type
try {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $s = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    $w = New-Object Windows.Storage.Streams.DataWriter $s
    $w.WriteBytes($bytes)
    Await ($w.StoreAsync()) ([uint32]) | Out-Null
    $w.DetachStream() | Out-Null
    $s.Seek(0)
    Write-Output ("B_SIZE=" + $s.Size)
    $dec2 = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($s)) ([Windows.Graphics.Imaging.BitmapDecoder])
    Write-Output ("B_OK " + $dec2.PixelWidth + "x" + $dec2.PixelHeight)
} catch {
    Write-Output ("B_FAIL " + $_.Exception.InnerException.InnerException.Message)
}
