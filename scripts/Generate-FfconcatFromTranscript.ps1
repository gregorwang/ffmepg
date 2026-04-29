[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TranscriptPath,

    [Parameter(Mandatory = $true)]
    [string]$MediaPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

$absoluteTranscriptPath = [System.IO.Path]::GetFullPath($TranscriptPath)
$absoluteMediaPath = [System.IO.Path]::GetFullPath($MediaPath)
$absoluteOutputPath = [System.IO.Path]::GetFullPath($OutputPath)

if (-not (Test-Path -LiteralPath $absoluteTranscriptPath)) {
    throw "Transcript 文件不存在：$absoluteTranscriptPath"
}

if (-not (Test-Path -LiteralPath $absoluteMediaPath)) {
    throw "媒体文件不存在：$absoluteMediaPath"
}

$transcript = Get-Content -LiteralPath $absoluteTranscriptPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $transcript.Segments -or $transcript.Segments.Count -eq 0) {
    throw "Transcript 缺少 Segments 或为空。"
}

$outputDirectory = Split-Path -Parent $absoluteOutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$normalizedMediaPath = $absoluteMediaPath.Replace('\', '/')
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("ffconcat version 1.0") | Out-Null

foreach ($segment in $transcript.Segments) {
    $start = [double]$segment.Start
    $end = [double]$segment.End

    if ($end -le $start) {
        continue
    }

    $lines.Add("file '$normalizedMediaPath'") | Out-Null
    $lines.Add(("inpoint {0}" -f $start.ToString([System.Globalization.CultureInfo]::InvariantCulture))) | Out-Null
    $lines.Add(("outpoint {0}" -f $end.ToString([System.Globalization.CultureInfo]::InvariantCulture))) | Out-Null
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($absoluteOutputPath, $lines, $utf8NoBom)

[pscustomobject]@{
    OutputPath = $absoluteOutputPath
    SegmentCount = [Math]::Max(0, ($lines.Count - 1) / 3)
}
