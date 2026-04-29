[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [ValidateSet("cu118", "cu126", "cu129")]
    [string]$CudaVariant = "cu118",
    [switch]$UseCpu,
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $scriptDir ".venv"

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Action
    )

    Write-Host "==> $Title" -ForegroundColor Cyan
    & $Action
}

if (-not $SkipVenv) {
    Invoke-Step "创建虚拟环境" {
        & $PythonExe -m venv $venvDir
    }
    $PythonExe = Join-Path $venvDir "Scripts\python.exe"
}

Invoke-Step "升级 pip/setuptools/wheel" {
    & $PythonExe -m pip install --upgrade pip setuptools wheel
}

if ($UseCpu) {
    Invoke-Step "安装 PaddlePaddle CPU" {
        & $PythonExe -m pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
    }
}
else {
    $paddleIndex = "https://www.paddlepaddle.org.cn/packages/stable/$CudaVariant/"
    Invoke-Step "安装 PaddlePaddle GPU ($CudaVariant)" {
        & $PythonExe -m pip install paddlepaddle-gpu==3.2.2 -i $paddleIndex
    }
}

Invoke-Step "安装项目依赖" {
    & $PythonExe -m pip install -e $scriptDir
}

Invoke-Step "运行 Paddle 安装校验" {
    & $PythonExe -c "import paddle; paddle.utils.run_check()"
}

Write-Host ""
Write-Host "安装完成。" -ForegroundColor Green
if (-not $SkipVenv) {
    Write-Host "激活命令：`n$venvDir\Scripts\Activate.ps1" -ForegroundColor Yellow
}
Write-Host "如果未找到 ffmpeg.exe，请把 ffmpeg 放入 PATH，或运行时传 --ffmpeg-bin。" -ForegroundColor Yellow
