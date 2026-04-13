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
- `AnimeTranscoder.Cli\\bin\\Debug\\net8.0-windows\\AnimeTranscoder.Cli.exe`
- `dist\\AnimeTranscoder-win-x64\\AnimeTranscoder.exe`（运行发布脚本后生成）

本目录可直接执行：

```powershell
dotnet restore
dotnet build
dotnet test
dotnet run --project .\AnimeTranscoder.csproj
dotnet run --project .\AnimeTranscoder.Cli\AnimeTranscoder.Cli.csproj -- help
```

## 项目结构

当前仓库已经拆成三层：

- `AnimeTranscoder.csproj`
  - 现有 `WPF` 桌面程序
- `AnimeTranscoder.Core/AnimeTranscoder.Core.csproj`
  - 共享模型、服务、工作流与协议
- `AnimeTranscoder.Cli/AnimeTranscoder.Cli.csproj`
  - 独立命令行入口

根目录的 `dotnet build` / `dotnet test` 现在通过 `AnimeTranscoder.slnx` 执行。

## CLI 能力

当前 CLI 已支持以下基础命令：

- `probe --input <path>`
- `audio extract --input <path> --output <path>`
- `audio detect-silence --input <path>`
- `project init --input <path> --project <path.atproj>`
- `audio export-work --project <path.atproj>`
- `transcript import --project <path.atproj> --input <transcript.json>`
- `selection import --project <path.atproj> --input <selection.json>`
- `audio render-selection --project <path.atproj> --output <path>`

示例：

```powershell
dotnet run --project .\AnimeTranscoder.Cli\AnimeTranscoder.Cli.csproj -- probe --input .\scratch\cli-smoke\sample.mp4

dotnet run --project .\AnimeTranscoder.Cli\AnimeTranscoder.Cli.csproj -- project init `
  --input .\scratch\cli-smoke\sample.mp4 `
  --project .\scratch\cli-smoke\demo.atproj
```

`*.atproj` 当前只保存：

- 输入媒体路径
- 工作目录
- 工作音频路径
- transcript / selection 文件路径
- 当前状态与时间戳

它不会内嵌 transcript 或 selection 正文。

## GUI 音频项目能力

当前 `WPF` 音频页已经接入共享 workflow，并支持一条最小音频项目链路：

- 选择音频源
- 创建或加载 `*.atproj`
- 导出工作音频
- 导入 `transcript.json`
- 导入 `selection.json`
- 按选择结果渲染输出

这条 GUI 链路与 CLI 共用同一个 `Core` 工作流层：

- `AudioProcessingWorkflow`
- `ProjectAudioWorkflow`

## GUI 主转码队列能力

当前主转码队列也已经接入共享 workflow：

- GUI 入口仍然是原有队列按钮和列表
- `MainViewModel` 通过 `TranscodeQueueWorkflow` 调用共享主链路
- 叠加素材准备目前仍由 GUI 侧注入，避免在这一阶段强行迁移 `DanmakuPreparationService`
- 旧的内联队列实现仍保留为回滚路径

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
