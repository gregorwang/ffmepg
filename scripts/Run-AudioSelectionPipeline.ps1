[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [ValidateSet("PreserveTimeline", "Concat")]
    [string]$Mode = "Concat",

    [string]$SelectionPath = "",

    [string[]]$IncludeRegex = @(),

    [string[]]$ExcludeRegex = @(),

    [double]$MinDurationSeconds = 0.15,

    [switch]$RegenerateTranscript
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$cliPath = Join-Path $repoRoot "AnimeTranscoder.Cli\bin\Debug\net8.0-windows\AnimeTranscoder.Cli.exe"
$selectionScriptPath = Join-Path $repoRoot "scripts\Generate-SelectionFromTranscript.ps1"
$absoluteProjectPath = [System.IO.Path]::GetFullPath($ProjectPath)
$projectDirectory = Split-Path -Parent $absoluteProjectPath

if (-not (Test-Path -LiteralPath $cliPath)) {
    throw "CLI 可执行文件不存在：$cliPath"
}

if (-not (Test-Path -LiteralPath $selectionScriptPath)) {
    throw "Selection 生成脚本不存在：$selectionScriptPath"
}

if (-not (Test-Path -LiteralPath $absoluteProjectPath)) {
    throw "项目文件不存在：$absoluteProjectPath"
}

if ([string]::IsNullOrWhiteSpace($SelectionPath)) {
    $SelectionPath = Join-Path $projectDirectory "selection.json"
}

$projectJson = Get-Content -LiteralPath $absoluteProjectPath -Raw -Encoding UTF8 | ConvertFrom-Json
$transcriptPath = [string]$projectJson.TranscriptPath

if ($RegenerateTranscript -or [string]::IsNullOrWhiteSpace($transcriptPath) -or -not (Test-Path -LiteralPath $transcriptPath)) {
    & $cliPath transcript generate --project $absoluteProjectPath --progress jsonl
    if ($LASTEXITCODE -ne 0) {
        throw "transcript generate 失败，退出码：$LASTEXITCODE"
    }

    $projectJson = Get-Content -LiteralPath $absoluteProjectPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $transcriptPath = [string]$projectJson.TranscriptPath
}

if ([string]::IsNullOrWhiteSpace($transcriptPath) -or -not (Test-Path -LiteralPath $transcriptPath)) {
    throw "transcript.json 不存在。"
}

$selectionArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $selectionScriptPath,
    "-TranscriptPath", $transcriptPath,
    "-OutputPath", $SelectionPath,
    "-MinDurationSeconds", $MinDurationSeconds
)

foreach ($pattern in $IncludeRegex) {
    $selectionArgs += @("-IncludeRegex", $pattern)
}

foreach ($pattern in $ExcludeRegex) {
    $selectionArgs += @("-ExcludeRegex", $pattern)
}

& powershell @selectionArgs
if ($LASTEXITCODE -ne 0) {
    throw "Generate-SelectionFromTranscript.ps1 执行失败，退出码：$LASTEXITCODE"
}

& $cliPath selection import --project $absoluteProjectPath --input $SelectionPath
if ($LASTEXITCODE -ne 0) {
    throw "selection import 失败，退出码：$LASTEXITCODE"
}

& $cliPath audio render-selection --project $absoluteProjectPath --output $OutputPath --mode $Mode --progress jsonl
if ($LASTEXITCODE -ne 0) {
    throw "audio render-selection 失败，退出码：$LASTEXITCODE"
}
