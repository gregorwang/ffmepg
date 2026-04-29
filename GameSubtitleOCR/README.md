# GameSubtitleOCR

独立的 Python OCR 子项目，用于从游戏视频中提取硬编码中文字幕，并生成 `SRT` 字幕文件。

技术栈：

- `PaddleOCR` / `PP-OCRv5`
- `FFmpeg`
- `OpenCV`

支持能力：

- Windows 安装脚本，自动创建虚拟环境并安装 `paddlepaddle-gpu`、`paddleocr`、`opencv-python`、`ffmpeg-python`
- 采样若干视频帧，自动检测字幕区域并输出推荐裁剪坐标
- 对多组图像预处理参数进行 OCR 调优，输出 `JSON + Markdown` 对比报告
- 按最佳参数流式抽取全视频字幕
- 帧间去重、相似文本合并、时间戳生成
- 输出标准 `SRT`

已验证的一组较稳版本组合：

- `paddlepaddle==3.2.0`（CPU 测试）
- `paddleocr==3.3.3`

## 目录

```text
GameSubtitleOCR/
  install_windows.ps1
  pyproject.toml
  README.md
  src/game_subtitle_ocr/
```

## 环境要求

- Windows
- Python 3.10+
- NVIDIA GPU + CUDA
- `ffmpeg.exe` 可用

如果 `ffmpeg.exe` 不在 `PATH` 中，可以在命令行里显式传 `--ffmpeg-bin C:\path\to\ffmpeg.exe`。

## 安装

在 `GameSubtitleOCR` 目录执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_windows.ps1
```

如果你的 CUDA 不是默认的 `11.8`，可以显式指定：

```powershell
.\install_windows.ps1 -CudaVariant cu126
.\install_windows.ps1 -CudaVariant cu129
```

如果只想先用 CPU 调试：

```powershell
.\install_windows.ps1 -UseCpu
```

安装完成后激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 用法

### 一键跑完整流程

```powershell
game-subtitle-ocr run `
  --input "C:\video\ghost_of_yotei.mp4" `
  --output-dir ".\runs\ghost_of_yotei"
```

默认会输出：

- `region_report.json`
- `tuning_report.json`
- `tuning_report.md`
- `extraction_report.json`
- `ghost_of_yotei_chinese.srt`

### 只做字幕区域检测

```powershell
game-subtitle-ocr detect-region `
  --input "C:\video\ghost_of_yotei.mp4" `
  --output-dir ".\runs\detect_only"
```

### 只做参数调优

```powershell
game-subtitle-ocr tune `
  --input "C:\video\ghost_of_yotei.mp4" `
  --crop-json ".\runs\detect_only\region_report.json" `
  --output-dir ".\runs\tune_only"
```

### 用已有区域和参数做全量抽取

```powershell
game-subtitle-ocr extract `
  --input "C:\video\ghost_of_yotei.mp4" `
  --crop-json ".\runs\detect_only\region_report.json" `
  --profile-json ".\runs\tune_only\tuning_report.json" `
  --output-dir ".\runs\extract_only"
```

## 主要参数

- `--device gpu|cpu`
- `--model-profile mobile|server`
- `--sample-count 24`
- `--fps 3.0`
- `--min-confidence 0.45`
- `--similarity-threshold 0.86`
- `--max-gap-frames 1`

## 输出说明

`region_report.json` 中的推荐裁剪坐标格式：

```json
{
  "recommended_crop": {
    "x": 220,
    "y": 890,
    "width": 1480,
    "height": 160
  }
}
```

`tuning_report.json` 会包含 `best_profile`，`extract` 和 `run` 都可以直接读取。

## 说明

- 本项目优先针对“底部单行或双行硬编码中文字幕”。
- 识别质量受视频压缩、描边样式、运动模糊、UI 叠层和字幕阴影影响较大。
- 若自动检测区域偏大或偏小，可手动传 `--crop x,y,w,h` 覆盖。
