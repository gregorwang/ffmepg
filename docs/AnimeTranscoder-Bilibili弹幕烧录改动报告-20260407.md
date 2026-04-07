# AnimeTranscoder Bilibili 弹幕烧录改动报告

日期：2026-04-07

## 1. 需求目标

本次改动目标是在不推翻当前仓库架构的前提下，为 `AnimeTranscoder` 增加一条新的可选工作流：

- 给定常见命名格式的本地番剧视频文件
- 自动识别作品名与集号
- 自动映射到对应 Bilibili 番剧
- 自动解析对应分集 `cid`
- 自动下载 XML 弹幕
- 自动生成 ASS
- 自动通过 `ffmpeg` 硬烧录输出视频

同时满足以下工程约束：

- 优先复用当前仓库已有抽象和工具类
- 不做无关大重构
- 不引入运行时 AI 依赖
- 所有外部访问都有失败处理与日志
- 为番名匹配、番剧映射、`cid` 解析、XML 下载、ASS 生成、FFmpeg 烧录保留清晰边界
- 批量转码场景考虑缓存，避免重复解析

## 2. 现有仓库复用情况

本次改动没有新建一套独立转码框架，而是接入现有主链路：

- 配置模型与持久化：
  - `Models/AppSettings.cs`
  - `Services/JsonSettingsService.cs`
- 日志：
  - `Infrastructure/AppFileLogger.cs`
- 转码执行：
  - `Services/FfmpegCommandBuilder.cs`
  - `Services/FfmpegRunner.cs`
- 队列编排：
  - `ViewModels/MainViewModel.cs`
- 窗口注入与 UI：
  - `Views/MainWindow.xaml`
  - `Views/MainWindow.xaml.cs`

这保证了新功能仍然使用同一套：

- 设置保存机制
- 任务队列
- 日志输出
- 输出校验
- 编码器选择
- `ffmpeg` 执行和进度上报

## 3. 新增模块边界

本次改动按阶段拆分成以下服务：

### 3.1 番名匹配

- `Services/AnimeEpisodeParserService.cs`

职责：

- 从常见番剧文件名中解析作品名
- 解析集号
- 尝试识别季信息
- 生成用于搜索的标准化关键字

支持样例：

- `[SubsPlease] Sousou no Frieren - 03 (1080p) [A1B2C3D4].mkv`
- `葬送的芙莉莲 第2季 第05话.mkv`
- `Title S01E03.mkv`

### 3.2 番剧映射

- `Services/DanmakuMappingConfigService.cs`
- `Services/BangumiMappingService.cs`
- `Config/anime-danmaku-mappings.json`

职责：

- 优先读取本地映射配置
- 若配置未命中，则调用 Bilibili 搜索接口
- 对搜索结果做简单打分，选出最可能的番剧

映射文件用于覆盖这些不稳定场景：

- 标题存在多个别名
- 文件名缩写过重
- 需要强制指定 `season_id`
- 需要对某集做 `cid` 或 `ep_id` 覆盖

### 3.3 cid 解析

- `Services/BilibiliCidResolverService.cs`

职责：

- 在番剧详情里优先选择正片分集
- 根据集号匹配分集
- 支持从本地映射配置覆盖 `cid`
- 输出清晰失败原因

### 3.4 XML 下载

- `Services/DanmakuXmlService.cs`
- `Services/BilibiliBangumiClient.cs`

职责：

- 调用 Bilibili 公开接口
- 下载对应 `cid` 的 XML 弹幕
- 对所有 HTTP 失败做异常与文件日志记录

### 3.5 ASS 生成

- `Services/DanmakuAssGeneratorService.cs`

职责：

- 解析 XML 中的弹幕节点
- 生成 ASS
- 支持字号、密度、时间偏移、屏蔽词、特殊弹幕过滤
- 对滚动、顶部、底部弹幕做基础布局

### 3.6 FFmpeg 烧录

- `Services/DanmakuBurnCommandBuilder.cs`
- `Services/FfmpegCommandBuilder.cs`

职责：

- 复用现有编码策略
- 在保留原内嵌字幕烧录路径的同时，新增外部 ASS 烧录能力
- 使用原有 `FfmpegRunner` 执行

### 3.7 工作流编排

- `Services/DanmakuPreparationService.cs`
- `ViewModels/MainViewModel.cs`

职责：

- 统一组织从文件名解析到 ASS 生成的前置链路
- 在队列模式下按阶段更新状态与日志
- 把失败定位到具体阶段

## 4. 新增数据模型

新增模型如下：

- `Models/AnimeEpisodeMatch.cs`
  - 文件名解析结果
- `Models/BangumiSeasonInfo.cs`
  - 番剧与分集信息
- `Models/DanmakuComment.cs`
  - 弹幕行模型
- `Models/DanmakuMappingConfig.cs`
  - 本地映射配置模型
- `Models/DanmakuPreparationResult.cs`
  - 弹幕准备链路的统一结果
- `Models/SubtitleSourceModes.cs`
  - 字幕来源模式常量

## 5. 配置项改动

在 `Models/AppSettings.cs` 中新增以下配置项：

- `SubtitleSourceMode`
  - `embedded`
  - `bilibili_danmaku`
- `DanmakuMappingPath`
- `DanmakuFontName`
- `DanmakuFontSize`
- `DanmakuDensity`
- `DanmakuTimeOffsetSeconds`
- `DanmakuBlockKeywords`
- `DanmakuFilterSpecialTypes`

默认值：

- 弹幕来源：`embedded`
- 映射文件：`Config/anime-danmaku-mappings.json`
- 字体：`Microsoft YaHei`
- 字号：`46`
- 密度：`0.65`
- 时间偏移：`0`
- 特殊弹幕过滤：开启

## 6. UI 改动

在 `Views/MainWindow.xaml` 新增“弹幕配置”分组，允许直接设置：

- 字幕来源
- 映射配置路径
- 字体名称
- 字号
- 密度
- 时间偏移
- 屏蔽词
- 是否过滤特殊弹幕

同时将文件选择过滤器从仅 `mkv` 扩展为常见视频格式。

## 7. 队列主链路改动

`ViewModels/MainViewModel.cs` 的 `StartQueueAsync()` 现在分成两条路径：

### 7.1 原有路径

当 `SubtitleSourceMode = embedded` 时：

- 保持现有内嵌字幕分析与自动选择逻辑
- 保持原行为不变

### 7.2 新弹幕路径

当 `SubtitleSourceMode = bilibili_danmaku` 时：

1. 媒体探测
2. 调用 `DanmakuPreparationService`
3. 获取 ASS 路径
4. 通过 `DanmakuBurnCommandBuilder` 构造命令
5. 使用现有 `FfmpegRunner` 烧录输出
6. 继续走现有输出校验和历史记录逻辑

为避免与内嵌字幕输出文件冲突，弹幕模式输出文件名会自动加后缀：

- `原文件名-danmaku.mp4`

## 8. 缓存设计

新增：

- `Services/DanmakuCacheService.cs`

缓存目录：

- `%AppData%/AnimeTranscoder/cache/danmaku`

缓存内容：

- 番剧搜索结果
- 番剧详情结果
- XML 原文
- ASS 结果

缓存收益：

- 批量处理同一番剧不同分集时减少重复请求
- 重跑失败任务时减少重复解析
- 调整输出流程时减少重复下载 XML

## 9. 错误处理与日志

本次改动重点保证失败阶段可定位。

日志会输出以下阶段信息：

- 番名匹配
- 番剧映射
- `cid` 解析
- XML 下载
- ASS 生成
- FFmpeg 烧录

失败时，任务状态说明会直接体现阶段，例如：

- `弹幕番剧映射失败`
- `弹幕cid 解析失败`
- `弹幕XML 下载失败`
- `弹幕ASS 生成失败`

外部 HTTP 请求失败也会记录到文件日志。

## 10. 最小测试与验证

新增测试项目：

- `AnimeTranscoder.Tests/AnimeTranscoder.Tests.csproj`

测试文件：

- `AnimeTranscoder.Tests/AnimeEpisodeParserServiceTests.cs`
- `AnimeTranscoder.Tests/DanmakuAssGeneratorServiceTests.cs`

覆盖内容：

- 常见番剧文件名解析
- 中文季/集文件名解析
- XML 弹幕过滤
- ASS 文本输出结构

本地执行结果：

```powershell
dotnet build AnimeTranscoder.csproj
dotnet test AnimeTranscoder.Tests\AnimeTranscoder.Tests.csproj
```

结果：

- `build` 通过
- `test` 通过
- 共 `4` 个测试，`4` 个通过

## 11. 使用方法

### 11.1 基本使用

1. 打开主程序
2. 在“弹幕配置”中把“字幕来源”切换为 `Bilibili XML 弹幕`
3. 根据需要调整：
   - 字号
   - 密度
   - 时间偏移
   - 屏蔽词
   - 特殊弹幕过滤
4. 如有必要，在 `Config/anime-danmaku-mappings.json` 增加标题映射
5. 添加视频文件并开始队列

### 11.2 映射配置示例

```json
{
  "mappings": [
    {
      "name": "葬送的芙莉莲",
      "searchKeyword": "葬送的芙莉莲",
      "seasonId": 46089,
      "localTitles": [
        "Sousou no Frieren",
        "Frieren",
        "葬送的芙莉莲"
      ],
      "episodeOverrides": []
    }
  ]
}
```

## 12. 已知限制

当前实现仍有这些已知限制：

- 依赖 Bilibili 公开接口可访问且返回结构稳定
- 文件名解析针对常见单集命名，不保证覆盖 OVA、SP、合集、极端缩写名
- ASS 布局是轻量实现，不是完整弹幕引擎
- 特效弹幕与高级定位弹幕默认过滤
- 目前测试主要覆盖纯本地逻辑，未包含仓库内真实样片的端到端联调

## 13. 本次改动涉及文件

### 修改文件

- `AnimeTranscoder.csproj`
- `Models/AppSettings.cs`
- `Services/FfmpegCommandBuilder.cs`
- `Services/JsonSettingsService.cs`
- `Services/UserDialogService.cs`
- `ViewModels/MainViewModel.cs`
- `Views/MainWindow.xaml`
- `Views/MainWindow.xaml.cs`

### 新增文件

- `Config/anime-danmaku-mappings.json`
- `Models/AnimeEpisodeMatch.cs`
- `Models/BangumiSeasonInfo.cs`
- `Models/DanmakuComment.cs`
- `Models/DanmakuMappingConfig.cs`
- `Models/DanmakuPreparationResult.cs`
- `Models/SubtitleSourceModes.cs`
- `Services/AnimeEpisodeParserService.cs`
- `Services/BangumiMappingService.cs`
- `Services/BilibiliBangumiClient.cs`
- `Services/BilibiliCidResolverService.cs`
- `Services/DanmakuAssGeneratorService.cs`
- `Services/DanmakuBurnCommandBuilder.cs`
- `Services/DanmakuCacheService.cs`
- `Services/DanmakuMappingConfigService.cs`
- `Services/DanmakuPreparationService.cs`
- `Services/DanmakuXmlService.cs`
- `AnimeTranscoder.Tests/AnimeTranscoder.Tests.csproj`
- `AnimeTranscoder.Tests/AnimeEpisodeParserServiceTests.cs`
- `AnimeTranscoder.Tests/DanmakuAssGeneratorServiceTests.cs`

## 14. 结论

本次改动是在现有仓库架构上增量实现的，没有破坏原有内嵌字幕转码路径，新增了一条可配置、可缓存、可定位失败阶段的 Bilibili XML 弹幕硬烧录工作流。

从工程角度看，本次改动已经满足以下目标：

- 保留清晰的阶段边界
- 复用现有抽象和执行框架
- 对批量场景增加缓存
- 对外部访问增加失败处理和日志
- 提供最小自动化测试

