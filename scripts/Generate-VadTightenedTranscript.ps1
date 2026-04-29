[CmdletBinding(DefaultParameterSetName = "FromLog")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "FromLog")]
    [string]$VadLogPath,

    [Parameter(Mandatory = $true, ParameterSetName = "FromAudio")]
    [string]$AudioPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string]$VadExecutablePath = "",

    [string]$VadModelPath = "",

    [double]$GapSeconds = 3.5,

    [double]$EndPaddingSeconds = 0.35,

    [double]$StartBiasSeconds = 0.35,

    [double]$MinDurationSeconds = 0.6,

    [string]$IdPrefix = "speech_",

    [string]$PlaceholderText = "[speech]",

    [string]$Language = "en",

    [string]$Source = "vad-tightened-g3",

    [string]$Channel = "mono",

    [switch]$UseGpu,

    [switch]$KeepVadLog
)

$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    return [System.IO.Path]::GetFullPath($PathValue)
}

function Get-VadSegmentsFromLog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LogPath
    )

    $pattern = 'VAD segment \d+: start = (?<start>\d+(?:\.\d+)?), end = (?<end>\d+(?:\.\d+)?)'
    $segments = New-Object System.Collections.Generic.List[object]

    foreach ($line in [System.IO.File]::ReadLines($LogPath)) {
        $match = [System.Text.RegularExpressions.Regex]::Match($line, $pattern)
        if (-not $match.Success) {
            continue
        }

        $start = [double]::Parse($match.Groups["start"].Value, [System.Globalization.CultureInfo]::InvariantCulture)
        $end = [double]::Parse($match.Groups["end"].Value, [System.Globalization.CultureInfo]::InvariantCulture)

        if ($end -le $start) {
            continue
        }

        $segments.Add([pscustomobject]@{
            Start = $start
            End = $end
        })
    }

    return $segments
}

function Merge-VadSegments {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[object]]$Segments,

        [Parameter(Mandatory = $true)]
        [double]$MergeGapSeconds
    )

    $merged = New-Object System.Collections.Generic.List[object]
    if ($Segments.Count -eq 0) {
        return $merged
    }

    $ordered = $Segments | Sort-Object Start, End
    $currentStart = [double]$ordered[0].Start
    $currentEnd = [double]$ordered[0].End

    for ($index = 1; $index -lt $ordered.Count; $index++) {
        $segment = $ordered[$index]
        $start = [double]$segment.Start
        $end = [double]$segment.End

        if (($start - $currentEnd) -le ($MergeGapSeconds + 0.0001)) {
            if ($end -gt $currentEnd) {
                $currentEnd = $end
            }
            continue
        }

        $merged.Add([pscustomobject]@{
            Start = $currentStart
            End = $currentEnd
        })

        $currentStart = $start
        $currentEnd = $end
    }

    $merged.Add([pscustomobject]@{
        Start = $currentStart
        End = $currentEnd
    })

    return $merged
}

function Write-VadLogFromAudio {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ExecutablePath,

        [Parameter(Mandatory = $true)]
        [string]$InputAudioPath,

        [Parameter(Mandatory = $true)]
        [string]$ModelPath,

        [Parameter(Mandatory = $true)]
        [string]$DestinationLogPath,

        [switch]$EnableGpu
    )

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()

    try {
        $argumentList = @(
            "--file", $InputAudioPath,
            "--vad-model", $ModelPath,
            "--vad-threshold", "0.5",
            "--vad-min-speech-duration-ms", "250",
            "--vad-min-silence-duration-ms", "100",
            "--vad-max-speech-duration-s", "20",
            "--vad-speech-pad-ms", "30",
            "--vad-samples-overlap", "0.1"
        )

        if ($EnableGpu) {
            $argumentList += "--use-gpu"
        }

        $process = Start-Process -FilePath $ExecutablePath -ArgumentList $argumentList -Wait -PassThru -NoNewWindow `
            -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

        $combinedOutput = @()
        if (Test-Path -LiteralPath $stdoutPath) {
            $combinedOutput += Get-Content -LiteralPath $stdoutPath -Encoding UTF8
        }
        if (Test-Path -LiteralPath $stderrPath) {
            $combinedOutput += Get-Content -LiteralPath $stderrPath -Encoding UTF8
        }

        $combinedOutput | Set-Content -LiteralPath $DestinationLogPath -Encoding UTF8

        if ($process.ExitCode -ne 0 -and -not ($combinedOutput -match "Detected \d+ speech segments")) {
            throw "VAD 进程失败，退出码：$($process.ExitCode)"
        }
    }
    finally {
        if (Test-Path -LiteralPath $stdoutPath) {
            Remove-Item -LiteralPath $stdoutPath -Force
        }
        if (Test-Path -LiteralPath $stderrPath) {
            Remove-Item -LiteralPath $stderrPath -Force
        }
    }
}

$absoluteOutputPath = Resolve-AbsolutePath -PathValue $OutputPath
$outputDirectory = Split-Path -Parent $absoluteOutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$resolvedAudioPath = ""
$resolvedVadLogPath = ""

if ($PSCmdlet.ParameterSetName -eq "FromAudio") {
    $resolvedAudioPath = Resolve-AbsolutePath -PathValue $AudioPath
    if (-not (Test-Path -LiteralPath $resolvedAudioPath)) {
        throw "音频文件不存在：$resolvedAudioPath"
    }

    if ([string]::IsNullOrWhiteSpace($VadExecutablePath)) {
        throw "缺少 VadExecutablePath。"
    }

    if ([string]::IsNullOrWhiteSpace($VadModelPath)) {
        throw "缺少 VadModelPath。"
    }

    $resolvedVadExecutablePath = Resolve-AbsolutePath -PathValue $VadExecutablePath
    $resolvedVadModelPath = Resolve-AbsolutePath -PathValue $VadModelPath
    if (-not (Test-Path -LiteralPath $resolvedVadExecutablePath)) {
        throw "VAD 可执行文件不存在：$resolvedVadExecutablePath"
    }
    if (-not (Test-Path -LiteralPath $resolvedVadModelPath)) {
        throw "VAD 模型不存在：$resolvedVadModelPath"
    }

    $resolvedVadLogPath = [System.IO.Path]::ChangeExtension($absoluteOutputPath, ".vad.log.txt")
    Write-VadLogFromAudio -ExecutablePath $resolvedVadExecutablePath -InputAudioPath $resolvedAudioPath -ModelPath $resolvedVadModelPath `
        -DestinationLogPath $resolvedVadLogPath -EnableGpu:$UseGpu
}
else {
    $resolvedVadLogPath = Resolve-AbsolutePath -PathValue $VadLogPath
    if (-not (Test-Path -LiteralPath $resolvedVadLogPath)) {
        throw "VAD 日志不存在：$resolvedVadLogPath"
    }
}

$vadSegments = Get-VadSegmentsFromLog -LogPath $resolvedVadLogPath
if ($vadSegments.Count -eq 0) {
    throw "未从 VAD 日志中解析到任何 speech segment：$resolvedVadLogPath"
}

$mergedSegments = Merge-VadSegments -Segments $vadSegments -MergeGapSeconds $GapSeconds
$digits = [Math]::Max(4, ([string]$mergedSegments.Count).Length)
$outputSegments = New-Object System.Collections.Generic.List[object]
$segmentOrdinal = 0

for ($index = 0; $index -lt $mergedSegments.Count; $index++) {
    $segment = $mergedSegments[$index]
    $normalizedStart = [Math]::Max(0.0, [Math]::Floor(([double]$segment.Start + $StartBiasSeconds)))
    $normalizedEnd = [Math]::Round(([double]$segment.End + $EndPaddingSeconds), 2)

    if ($normalizedEnd -le $normalizedStart) {
        $normalizedEnd = [Math]::Round(([double]$segment.End), 2)
    }

    if (($normalizedEnd - $normalizedStart) -lt $MinDurationSeconds) {
        continue
    }

    $segmentOrdinal++
    $segmentId = "{0}{1}" -f $IdPrefix, $segmentOrdinal.ToString(("D{0}" -f $digits))

    $outputSegments.Add([ordered]@{
        Id = $segmentId
        Start = $normalizedStart
        End = $normalizedEnd
        Text = $PlaceholderText
        Language = $Language
        Speaker = $null
        Confidence = $null
        Source = $Source
        Overlap = $false
        Channel = $Channel
    })
}

if ([string]::IsNullOrWhiteSpace($resolvedAudioPath) -and $outputSegments.Count -gt 0) {
    $resolvedAudioPath = ""
}

$document = [ordered]@{
    Version = "1.0"
    AudioPath = $resolvedAudioPath
    Segments = $outputSegments
}

$document | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $absoluteOutputPath -Encoding UTF8

if (-not $KeepVadLog -and $PSCmdlet.ParameterSetName -eq "FromAudio" -and (Test-Path -LiteralPath $resolvedVadLogPath)) {
    Remove-Item -LiteralPath $resolvedVadLogPath -Force
}

$totalKeepDuration = [Math]::Round((($outputSegments | ForEach-Object { [double]$_.End - [double]$_.Start } | Measure-Object -Sum).Sum), 2)
[pscustomobject]@{
    OutputPath = $absoluteOutputPath
    VadLogPath = $resolvedVadLogPath
    SegmentCount = $outputSegments.Count
    TotalKeepDurationSeconds = $totalKeepDuration
}
