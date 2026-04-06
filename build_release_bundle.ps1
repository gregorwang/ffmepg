$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nativeRoot = Join-Path $projectRoot "native\AnimeMediaCore"
$releaseDir = Join-Path $projectRoot "dist\AnimeTranscoder-win-x64"
$zipPath = Join-Path $projectRoot "dist\AnimeTranscoder-win-x64.zip"
$toolsDir = Join-Path $releaseDir "tools\ffmpeg"
$dotnet = "C:\Users\汪家俊\.dotnet\dotnet.exe"
$ffmpegSource = "C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin"

Write-Host "准备生成 Release 包..."

if (-not (Test-Path "N:\")) {
    cmd /c "subst N: `"$nativeRoot`""
}

Write-Host "构建原生 AnimeMediaCore.dll..."
cmd /c "`"$nativeRoot\build_native_release.cmd`""

Write-Host "构建 WPF Release..."
& $dotnet build (Join-Path $projectRoot "AnimeTranscoder.csproj") -c Release

if (Test-Path $releaseDir) {
    Remove-Item $releaseDir -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null

$appOutput = Join-Path $projectRoot "bin\Release\net8.0-windows"
$nativeOutput = Join-Path $nativeRoot "build\Release-NMake\AnimeMediaCore.dll"

Write-Host "复制主程序与原生模块..."
Copy-Item -Path (Join-Path $appOutput "*") -Destination $releaseDir -Recurse -Force
Copy-Item -LiteralPath $nativeOutput -Destination (Join-Path $releaseDir "AnimeMediaCore.dll") -Force

Write-Host "复制 ffmpeg / ffprobe..."
Copy-Item -LiteralPath (Join-Path $ffmpegSource "ffmpeg.exe") -Destination (Join-Path $toolsDir "ffmpeg.exe") -Force
Copy-Item -LiteralPath (Join-Path $ffmpegSource "ffprobe.exe") -Destination (Join-Path $toolsDir "ffprobe.exe") -Force

Write-Host "写入发布说明..."
@"
AnimeTranscoder Release Bundle
==============================

版本: 0.1.0

包含内容:
- AnimeTranscoder.exe
- AnimeMediaCore.dll
- tools\ffmpeg\ffmpeg.exe
- tools\ffmpeg\ffprobe.exe

说明:
- 这是可直接运行的 Release 目录
- 首次启动后，设置文件位于 %APPDATA%\AnimeTranscoder\settings.json
- 任务历史位于 %APPDATA%\AnimeTranscoder\history.json
- 运行日志位于 %APPDATA%\AnimeTranscoder\logs\
- 如果要自动监听目录，请在程序设置中开启对应选项
"@ | Set-Content -Path (Join-Path $releaseDir "PACKAGE-README.txt") -Encoding UTF8

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

Write-Host "压缩发布目录..."
Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Release 包已生成: $releaseDir"
Write-Host "Release 压缩包已生成: $zipPath"
