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
Write-Output ("ENGINE=" + $(if ($engine) { $engine.RecognizerLanguage.LanguageTag } else { 'NULL' }))
if (-not $engine) { exit 2 }

Write-Output ("TESTPATH=" + $Path)
Write-Output ("EXISTS=" + (Test-Path -LiteralPath $Path))
try {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
    Write-Output "GOT_FILE"
} catch {
    Write-Output ("FAIL_GetFile: " + $_.Exception.ToString())
    Write-Output ("INNER: " + $_.Exception.InnerException)
    exit 3
}
try {
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    Write-Output "GOT_STREAM"
} catch {
    Write-Output ("FAIL_Open: " + $_.Exception.ToString())
    exit 4
}
try {
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    Write-Output ("GOT_DECODER " + $decoder.PixelWidth + "x" + $decoder.PixelHeight)
} catch {
    Write-Output ("FAIL_Decoder: " + $_.Exception.ToString())
    exit 5
}
try {
    $sb0 = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $bitmap = [Windows.Graphics.Imaging.SoftwareBitmap]::Convert($sb0, [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Premultiplied)
    Write-Output "GOT_BITMAP"
} catch {
    Write-Output ("FAIL_Bitmap: " + $_.Exception.ToString())
    exit 6
}
try {
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    Write-Output ("OCR_LINES=" + $result.Lines.Count)
    foreach ($line in $result.Lines) { Write-Output ("  | " + $line.Text) }
} catch {
    Write-Output ("FAIL_Ocr: " + $_.Exception.ToString())
    exit 7
}
