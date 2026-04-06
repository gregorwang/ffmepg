# AnimeTranscoder

Windows 原生桌面工具骨架，目标是把 `mkv` 动漫视频转成：

- `MP4`
- `H.264`
- `AAC LC`
- 硬字幕

当前版本已包含：

- `WPF + .NET 8` 项目骨架
- 文件队列模型
- 设置持久化
- `ffprobe` 探测服务
- 字幕轨自动选择服务
- `ffmpeg` 命令构造器
- 串行任务执行框架
- 中文化桌面 UI
- 任务历史筛选与 `json/txt` 导出
- 输入目录监听与稳定文件自动入队
- 可选的稳定文件自动开跑
- 原生 `AnimeMediaCore` 接入边界与自动回退
- 原生字幕分析与原生诊断抽帧入口
- 默认兼容优先输出策略（`AAC stereo`，面向 Windows/PS5 播放兼容性）
- 输出盘空间预检与增强型输出校验

## 当前约束

- MVP 只处理 `mkv`
- 默认输入目录：工作区根目录
- 默认输出目录：`mp4_hardsub_chs`
- 默认执行方式：串行
- 原生模块当前已可在本机构建并生成 `AnimeMediaCore.dll`
- `MP4` 输出默认启用 `faststart`，因此转码时需要预留额外磁盘空间用于文件头前移

## 本机环境说明

当前机器已安装 `.NET 8 SDK`，可以直接编译和运行 `WPF` 主程序。

当前可执行文件位置：

- `bin\\Debug\\net8.0-windows\\AnimeTranscoder.exe`
- `bin\\Release\\net8.0-windows\\AnimeTranscoder.exe`
- `dist\\AnimeTranscoder-win-x64\\AnimeTranscoder.exe`（运行发布脚本后生成）

本目录可直接执行：

```powershell
dotnet restore
dotnet build
dotnet run
```

## Release 出包

当前项目已经提供一键发布脚本：

```powershell
.\build_release_bundle.ps1
```

它会完成：

- 构建 `AnimeMediaCore.dll`
- 构建 `WPF Release`
- 复制主程序与原生模块到 `dist\AnimeTranscoder-win-x64`
- 打包 `ffmpeg.exe` 与 `ffprobe.exe` 到 `tools\ffmpeg`
- 生成压缩包 `dist\AnimeTranscoder-win-x64.zip`

## 当前新增原生能力

- `amc_analyze_subtitles_json`
  - 原生字幕轨分析
  - 文本字幕样本抽取
- `amc_probe_media_json`
  - 原生媒体探测
  - 时长读取
  - 字幕轨摘要返回
- `amc_validate_output_json`
  - 原生输出校验
  - 输入输出时长差计算
  - 匹配结果返回
- `amc_sample_frame_png_json`
  - 原生按时间点抽帧
  - 输出 `png`
  - `WPF` 侧可直接对选中任务导出诊断截图
- `amc_sample_frames_batch_json`
  - 原生批量抽帧
  - 一次导出多张巡检截图
  - `WPF` 侧可直接导出巡检三连图

## 当前新增巡检能力

- 巡检三连图会自动做亮度与对比度分析
- 主界面可直接查看每张截图的巡检结论
- 支持导出 `json/txt` 巡检报告
