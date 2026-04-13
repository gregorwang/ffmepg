[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TranscriptPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string[]]$IncludeRegex = @(),

    [string[]]$ExcludeRegex = @(),

    [double]$MinDurationSeconds = 0.15,

    [switch]$KeepEmptyText,

    [string]$DecisionSource = "local-selection-generator"
)

$ErrorActionPreference = "Stop"

function Test-AnyRegexMatch {
    param(
        [string]$Text,
        [string[]]$Patterns
    )

    foreach ($pattern in $Patterns) {
        if ([string]::IsNullOrWhiteSpace($pattern)) {
            continue
        }

        if ($Text -match $pattern) {
            return $true
        }
    }

    return $false
}

$absoluteTranscriptPath = [System.IO.Path]::GetFullPath($TranscriptPath)
if (-not (Test-Path -LiteralPath $absoluteTranscriptPath)) {
    throw "Transcript 文件不存在：$absoluteTranscriptPath"
}

$transcript = Get-Content -LiteralPath $absoluteTranscriptPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -eq $transcript.Segments) {
    throw "Transcript 缺少 Segments。"
}

$targetSegments = New-Object System.Collections.Generic.List[object]

foreach ($segment in $transcript.Segments) {
    $segmentId = [string]$segment.Id
    if ([string]::IsNullOrWhiteSpace($segmentId)) {
        continue
    }

    $text = ([string]$segment.Text).Trim()
    $start = [double]$segment.Start
    $end = [double]$segment.End
    $duration = [Math]::Max($end - $start, 0.0)

    $action = "Keep"
    $reason = "default_keep_non_empty_text"

    if ([string]::IsNullOrWhiteSpace($text) -and -not $KeepEmptyText) {
        $action = "Exclude"
        $reason = "empty_text"
    }
    elseif ($duration -lt $MinDurationSeconds) {
        $action = "Exclude"
        $reason = "too_short"
    }
    elseif ($IncludeRegex.Count -gt 0 -and -not (Test-AnyRegexMatch -Text $text -Patterns $IncludeRegex)) {
        $action = "Exclude"
        $reason = "include_regex_not_matched"
    }
    elseif ($ExcludeRegex.Count -gt 0 -and (Test-AnyRegexMatch -Text $text -Patterns $ExcludeRegex)) {
        $action = "Exclude"
        $reason = "exclude_regex_matched"
    }
    elseif ($IncludeRegex.Count -gt 0) {
        $reason = "include_regex_matched"
    }

    $targetSegments.Add([pscustomobject]@{
        SegmentId = $segmentId
        Action = $action
        Reason = $reason
    })
}

$selection = [ordered]@{
    Version = "1.0"
    TranscriptVersion = if ($transcript.Version) { [string]$transcript.Version } else { "1.0" }
    DecisionSource = $DecisionSource
    ConflictPolicy = "exclude_wins"
    TargetSegments = $targetSegments
}

$absoluteOutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $absoluteOutputPath
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$selection | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $absoluteOutputPath -Encoding UTF8
Write-Output $absoluteOutputPath
