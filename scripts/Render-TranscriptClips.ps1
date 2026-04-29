[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TranscriptPath,

    [Parameter(Mandatory = $true)]
    [string]$MediaPath,

    [Parameter(Mandatory = $true)]
    [string]$ClipsDirectory,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string]$ConcatPath,

    [string]$FfmpegPath = "ffmpeg",

    [string]$VideoEncoder = "h264_nvenc",

    [string]$NvencPreset = "p4",

    [int]$Cq = 30,

    [string]$AudioBitrate = "192k",

    [int]$StartIndex = 1,

    [int]$EndIndex = 0,

    [switch]$OverwriteClips,

    [switch]$SkipConcat
)

$ErrorActionPreference = "Stop"

$absoluteTranscriptPath = [System.IO.Path]::GetFullPath($TranscriptPath)
$absoluteMediaPath = [System.IO.Path]::GetFullPath($MediaPath)
$absoluteClipsDirectory = [System.IO.Path]::GetFullPath($ClipsDirectory)
$absoluteOutputPath = [System.IO.Path]::GetFullPath($OutputPath)

if ([string]::IsNullOrWhiteSpace($ConcatPath)) {
    $ConcatPath = Join-Path $absoluteClipsDirectory "clips.ffconcat"
}

$absoluteConcatPath = [System.IO.Path]::GetFullPath($ConcatPath)

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

New-Item -ItemType Directory -Path $absoluteClipsDirectory -Force | Out-Null

$segments = @($transcript.Segments)
$selectedSegments = New-Object System.Collections.Generic.List[object]

for ($i = 0; $i -lt $segments.Count; $i++) {
    $segmentIndex = $i + 1

    if ($segmentIndex -lt $StartIndex) {
        continue
    }

    if ($EndIndex -gt 0 -and $segmentIndex -gt $EndIndex) {
        break
    }

    $start = [double]$segments[$i].Start
    $end = [double]$segments[$i].End

    if ($end -le $start) {
        continue
    }

    $selectedSegments.Add([pscustomobject]@{
        Index = $segmentIndex
        Start = $start
        End = $end
        Duration = $end - $start
        ClipPath = Join-Path $absoluteClipsDirectory ("clip_{0:d4}.mp4" -f $segmentIndex)
    }) | Out-Null
}

if ($selectedSegments.Count -eq 0) {
    throw "当前筛选范围没有可渲染的有效片段。"
}

foreach ($segment in $selectedSegments) {
    $clipPath = $segment.ClipPath
    $needsRender = $OverwriteClips.IsPresent -or -not (Test-Path -LiteralPath $clipPath)

    if (-not $needsRender) {
        $existing = Get-Item -LiteralPath $clipPath
        if ($existing.Length -le 0) {
            $needsRender = $true
        }
    }

    if (-not $needsRender) {
        continue
    }

    $startText = $segment.Start.ToString([System.Globalization.CultureInfo]::InvariantCulture)
    $durationText = $segment.Duration.ToString([System.Globalization.CultureInfo]::InvariantCulture)

    & $FfmpegPath `
        -y `
        -hide_banner `
        -v error `
        -ss $startText `
        -i $absoluteMediaPath `
        -t $durationText `
        -map 0:v:0 `
        -map 0:a:0 `
        -c:v $VideoEncoder `
        -preset $NvencPreset `
        -tune hq `
        -cq $Cq `
        -b:v 0 `
        -pix_fmt yuv420p `
        -c:a aac `
        -b:a $AudioBitrate `
        $clipPath

    if ($LASTEXITCODE -ne 0) {
        throw "ffmpeg 渲染片段失败：#$($segment.Index) $clipPath"
    }
}

$concatLines = New-Object System.Collections.Generic.List[string]
$concatLines.Add("ffconcat version 1.0") | Out-Null

foreach ($segment in $selectedSegments) {
    if (-not (Test-Path -LiteralPath $segment.ClipPath)) {
        throw "缺少片段文件：$($segment.ClipPath)"
    }

    $normalizedClipPath = $segment.ClipPath.Replace('\', '/')
    $concatLines.Add("file '$normalizedClipPath'") | Out-Null
}

$concatDirectory = Split-Path -Parent $absoluteConcatPath
if (-not [string]::IsNullOrWhiteSpace($concatDirectory)) {
    New-Item -ItemType Directory -Path $concatDirectory -Force | Out-Null
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($absoluteConcatPath, $concatLines, $utf8NoBom)

if (-not $SkipConcat.IsPresent) {
    $outputDirectory = Split-Path -Parent $absoluteOutputPath
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }

    & $FfmpegPath `
        -y `
        -hide_banner `
        -v error `
        -f concat `
        -safe 0 `
        -i $absoluteConcatPath `
        -c copy `
        -movflags +faststart `
        $absoluteOutputPath

    if ($LASTEXITCODE -ne 0) {
        throw "ffmpeg 拼接失败：$absoluteOutputPath"
    }
}

[pscustomobject]@{
    SegmentCount = $selectedSegments.Count
    ClipsDirectory = $absoluteClipsDirectory
    ConcatPath = $absoluteConcatPath
    OutputPath = $absoluteOutputPath
}
