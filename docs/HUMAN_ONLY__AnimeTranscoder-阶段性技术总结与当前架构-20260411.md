# AnimeTranscoder 阶段性技术总结与当前架构

日期：2026-04-11

## 1. 最初目标与问题定义

这轮工作的最初目标，不是单纯给现有 `WPF` 软件加几个命令，而是为后续一个更大的功能目标建立可稳定自动化的底座。

最初目标可以拆成两层：

### 1.1 大前提：让软件可被命令行稳定驱动

目标不是让 `Codex`、`Claude Code` 这类命令行 coding agent 去模拟人类点击 GUI，而是让软件本身具备：

- 明确的 `CLI` 入口
- 稳定的输入输出协议
- 可被外部 agent 驱动的工作流接口
- GUI 与 CLI 复用同一套核心业务逻辑

换句话说，软件要从“只能人工点界面的桌面工具”，演进成“GUI 只是其中一个前端，核心能力可以被命令行、脚本、外部 AI、安全地复用”。

### 1.2 目标功能：本地语音转文本 + 外部 AI 选择 + 软件负责渲染

希望最终支持的功能链路是：

1. 从视频中提取工作音频
2. 在本地做语音识别，得到时间轴对齐的 transcript
3. 由外部 AI（例如 Codex）读取 transcript，挑出“游戏人物对白”而不是“主播说话”
4. 将选择结果回写给软件
5. 软件据此输出目标音频

这里的职责划分从一开始就定得很明确：

- 软件内部不嵌入大模型推理能力
- 语音转文字可以在本地做
- 外部 AI 只负责“读文本并做决策”
- 软件负责“项目管理、协议、执行、渲染、输出”

这个方向的核心价值，是把 AI 变成一个可替换的外部决策层，而不是把整个产品绑死在某个 AI SDK 或某套 prompt 上。

## 2. 核心技术决策

在进入实现前，已经明确了以下关键决策，这些决策决定了后续全部代码改动的方向。

### 2.1 不做 GUI 自动化，先做 CLI

放弃“让外部 agent 像人一样点桌面软件”的思路，改为：

- 软件提供正式 `CLI`
- CLI 和 GUI 共用同一套工作流层
- 外部 AI 通过文件协议和 CLI 命令与软件交互

原因：

- GUI 自动化脆弱，窗口状态、焦点、布局变化都会破坏调用稳定性
- CLI 更适合长任务、批处理、进度回传、取消和脚本集成
- 未来无论是本地 agent、调度器还是脚本，都会更容易接入

### 2.2 项目结构拆成三层

明确采用三项目结构：

- `AnimeTranscoder`  
  现有 `WPF` GUI 应用
- `AnimeTranscoder.Core`  
  共享模型、服务、workflow、协议
- `AnimeTranscoder.Cli`  
  独立命令行入口

不在 `WPF WinExe` 里硬塞 `AttachConsole` / `AllocConsole`。原因是：

- 生命周期复杂
- 控制台输出行为不稳定
- GUI/CLI 入口职责混乱
- 后续维护成本高

### 2.3 软件和外部 AI 通过文件协议交互

不是让 AI 操作内存对象，也不是让 AI 直接调用 GUI 控件，而是使用显式协议：

- `*.atproj`
- `transcript.json`
- `selection.json`

其中：

- `*.atproj` 只保存路径、元数据、当前状态
- `transcript.json` 和 `selection.json` 保持为独立文件
- 项目文件只引用它们的路径，不内嵌正文

这样做的好处：

- 项目文件不会无限膨胀
- transcript / selection 可以被外部工具单独读写
- CLI 与 GUI 共享同一份状态容器
- 后续兼容 `whisper.cpp` / `faster-whisper` 输出更容易

### 2.4 主转码队列迁移时保留回滚路径

主转码队列是现有产品的核心路径，迁移风险远高于音频项目链路。因此在迁移主队列时采用保守策略：

- 新建共享 workflow
- GUI 默认切到新 workflow
- 旧的内联队列实现保留为回滚路径

这是为了防止“主队列迁移失败直接把产品主功能打挂”。

### 2.5 `PrepareOverlayAssetsAsync` 先不强行整体搬进 Core

这一块和 `TranscodeJob`、弹幕准备、字幕轨选择、GUI 当前状态耦合很深。当前采用的是：

- 主链路进入 `Core`
- 叠加素材准备仍在 GUI 侧执行
- GUI 把“叠加准备结果”作为委托注入共享 workflow

这样可以先把大部分主队列逻辑统一掉，同时避免把高耦合区域在同一阶段硬拆。

## 3. 已完成的总体阶段

截至 2026-04-11，已经完成了三大阶段。

### 3.1 阶段一：CLI 底座与共享 Core 拆分

完成内容：

- 建立 `App + Core + Cli` 三层结构
- 把共享模型、服务、workflow 提取到 `Core`
- 让 WPF 项目引用 `Core`
- 新建独立 `CLI` 项目
- 定义 `*.atproj`、`transcript.json`、`selection.json` 的第一版协议
- 落第一批 CLI 命令

### 3.2 阶段二：GUI 音频项目工作流接入

完成内容：

- WPF 音频页接入共享 workflow
- 增加 GUI 的音频项目闭环
- GUI 与 CLI 共用 `ProjectAudioWorkflow`
- 把音频提取 / 静音检测接到 `AudioProcessingWorkflow`

### 3.3 阶段三：主转码队列 workflow 化

完成内容：

- 新建共享 `TranscodeQueueWorkflow`
- 主转码队列从 `MainViewModel` 抽出到共享 workflow
- GUI 侧通过映射 `TranscodeJob -> TranscodeTaskSpec` 接入新 workflow
- 保留旧队列实现作为回滚路径

## 4. 项目结构改造详情

### 4.1 解决方案结构

当前仓库已使用：

- `AnimeTranscoder.slnx`

项目分层如下：

#### `AnimeTranscoder.csproj`

职责：

- `WPF` 主应用
- 窗口、XAML、ViewModel、用户交互
- GUI 特有状态
- 局部仍保留高耦合逻辑，例如当前阶段的叠加素材准备

这个项目现在引用：

- `AnimeTranscoder.Core`

并且通过 `Compile Remove` 排除了大部分共享 `Models/Services/Workflows` 的重复编译，只保留 GUI 自己需要保留在 App 层的内容。

#### `AnimeTranscoder.Core/AnimeTranscoder.Core.csproj`

职责：

- 共享模型
- 共享服务
- 共享 workflow
- 共享协议

当前采用 linked file 的方式把根目录下共享源码链接进 `Core` 项目。这样做的现实好处是：

- 不必一次性移动所有文件物理位置
- 可以在保留现有目录组织的前提下，先完成分层和编译边界整理

#### `AnimeTranscoder.Cli/AnimeTranscoder.Cli.csproj`

职责：

- 独立命令行入口
- 解析参数
- 输出 JSON / JSONL
- 捕捉取消信号
- 调用 `Core` workflow

### 4.2 GUI composition root

GUI 不再在窗口代码里手工拼接全部依赖，而是增加了：

- `Composition/AppCompositionRoot.cs`

它负责：

- 创建共享 service
- 创建共享 workflow
- 构建 `MainViewModel`

这一步的意义很大，因为后续所有 GUI workflow 接入都以它为组合根，不再把依赖实例化散落在 `MainWindow.xaml.cs` 或其他 UI 代码里。

## 5. 已完成的共享模型与协议

### 5.1 音频项目协议

已经引入：

- `Models/AnimeProjectFile.cs`

用途：

- 保存输入媒体路径
- 保存工作目录
- 保存工作音频路径
- 保存 `transcript` 路径
- 保存 `selection` 路径
- 保存当前状态和时间戳

设计约束：

- 不内嵌 transcript 正文
- 不内嵌 selection 正文
- 只作为项目状态容器

### 5.2 Transcript / Selection 协议

已引入：

- `Models/TranscriptDocument.cs`
- `Models/TranscriptSegment.cs`
- `Models/SelectionDocument.cs`
- `Models/SelectionTargetSegment.cs`
- `Models/SelectionAction.cs`

这套协议用于：

- 接纳本地转写工具生成的 transcript
- 接纳外部 AI 的筛选结果
- 让软件据此执行渲染

### 5.3 主转码队列纯数据模型

主队列 workflow 化后新增：

- `Models/TranscodeTaskSpec.cs`
- `Models/TranscodeOverlayPreparationResult.cs`
- `Models/TranscodeTaskResult.cs`
- `Models/TranscodeQueueExecutionResult.cs`

其中最重要的是：

#### `TranscodeTaskSpec`

这是主队列在 `Core` 中的纯数据输入模型。它只包含执行转码必需的纯数据，例如：

- `TaskId`
- `InputPath`
- `OutputPath`
- `DanmakuInputPath`
- `DanmakuExcludedCommentKeys`

这样做的目的，是让 `Core` 不依赖 GUI 层的 `TranscodeJob`。

#### `TranscodeOverlayPreparationResult`

这是 GUI 侧叠加准备逻辑返回给 workflow 的共享结果，包含：

- 选中的字幕轨 ordinal
- 弹幕 ASS 路径
- 弹幕 XML 路径
- 弹幕数量统计
- 字幕分析来源
- 字幕种类摘要
- 弹幕来源摘要
- 失败信息

#### `TranscodeTaskResult`

这是 workflow 对单个任务执行后的完整结果快照，包含：

- 状态
- 进度
- 速度
- 消息
- 实际编码器
- 源时长
- 叠加准备结果摘要
- 是否删除源文件

### 5.4 统一进度模型

共享进度模型已统一为：

- `Models/WorkflowProgress.cs`

原本只包含：

- `Stage`
- `ProgressPercent`
- `Speed`
- `Message`
- `Timestamp`

现在为了支持主队列，还扩展了：

- `ItemId`
- `ItemPath`

这使得：

- CLI 可以对单任务或多任务输出统一进度事件
- GUI 可以把 workflow 进度正确路由回对应的 `TranscodeJob`

## 6. 已完成的共享服务与 workflow

### 6.1 已接入 Core 的音频工作流

#### `Workflows/AudioProcessingWorkflow.cs`

负责：

- 音频提取
- 静音检测
- 统一上报 `WorkflowProgress`

GUI 与 CLI 都已经接入它。

#### `Workflows/ProjectAudioWorkflow.cs`

负责：

- `project init`
- `audio export-work`
- `transcript import`
- `selection import`
- `audio render-selection`

这条链路已经是完整的共享工作流。

### 6.2 新增主转码共享工作流

#### `Workflows/TranscodeQueueWorkflow.cs`

这是这轮最重要的改动之一。

它当前负责：

1. 检查输入文件是否存在
2. 若不允许覆盖，则校验现有输出是否可跳过
3. 做输出盘空间预检
4. 做媒体探测
5. 解析视频编码器
6. 调用外部注入的叠加素材准备委托
7. 执行 `ffmpeg`
8. 执行输出校验
9. 按配置删除源文件
10. 回传任务结果与队列结果

#### 当前保持的队列语义

当前 workflow 明确保留了旧队列的核心行为：

- 串行执行
- 失败后继续后续任务
- 取消时当前任务标记为 `Cancelled`
- 每个任务结束后立即回写结果
- 输出校验通过才算成功
- 删除源文件只在成功后执行

这很关键，因为这次迁移的目标是“搬位置”，不是“改行为”。

## 7. CLI 已完成能力

CLI 入口位于：

- `AnimeTranscoder.Cli/Program.cs`

当前已支持：

- `probe`
- `audio extract`
- `audio detect-silence`
- `project init`
- `project show`
- `audio export-work`
- `transcript import`
- `selection import`
- `audio render-selection`

### 7.1 CLI 协议特点

当前 CLI 已具备这些特征：

- `stdout` 输出 JSON 结果
- 支持 `--progress jsonl` 时将进度事件输出到 `stderr`
- 捕捉 `Ctrl+C`
- 统一退出码

这意味着：

- 可以被 shell 脚本直接消费
- 可以被 agent 读取结构化结果
- 可以把进度和最终结果分离处理

### 7.2 CLI 已验证链路

已用真实样本跑通过：

1. `probe`
2. `project init`
3. `audio export-work`
4. `transcript import`
5. `selection import`
6. `audio render-selection`

并验证：

- `PreserveTimeline`
- `Concat`

两种输出模式都能工作。

## 8. GUI 已完成能力

### 8.1 音频页已接入共享项目工作流

当前 `WPF` 音频页已经支持：

- 选择音频源
- 创建 `*.atproj`
- 加载 `*.atproj`
- 导出工作音频
- 导入 `transcript.json`
- 导入 `selection.json`
- 按选择结果渲染音频

相关代码：

- `ViewModels/MainViewModel.AudioProject.cs`
- `Views/MainWindow.xaml`

### 8.2 GUI 音频提取和静音检测已走共享 workflow

原先音频提取 / 静音检测是 ViewModel 直接调用 service。现在已改为：

- ViewModel 调 `AudioProcessingWorkflow`
- workflow 调底层 service
- GUI 使用 `Progress<WorkflowProgress>` 接收进度

这一步已经把 GUI 音频链路和 CLI 音频链路统一到了同一层。

### 8.3 主转码队列已接入共享 workflow

新增文件：

- `ViewModels/MainViewModel.QueueWorkflow.cs`

当前行为：

- `StartQueueAsync()` 变成薄入口
- 默认走共享 workflow
- 旧队列保留为 `StartQueueLegacyAsync()`

为了降低风险，当前使用：

- `UseSharedQueueWorkflow = true`

作为内部回滚开关。

如果后续真实 GUI 回归发现问题，可以快速切回旧路径。

## 9. MainViewModel 侧的具体处理方式

### 9.1 为什么没有直接让 Core 接收 `TranscodeJob`

`TranscodeJob` 是 GUI 绑定对象，继承自 `ObservableObject`，上面挂着大量 UI 状态：

- `Status`
- `Progress`
- `Speed`
- `Message`
- `SubtitleStreamOrdinal`
- 弹幕摘要状态
- 绑定属性变更通知

如果让 `Core` 直接依赖它，会导致：

- `Core` 反向依赖 GUI 状态模型
- workflow 无法在 CLI 中复用
- 分层失效

因此当前采取的方案是：

- GUI 中保留 `TranscodeJob`
- 进入 workflow 前，将它映射为 `TranscodeTaskSpec`
- workflow 执行后，再把 `TranscodeTaskResult` 回写到 `TranscodeJob`

### 9.2 为什么叠加准备仍留在 GUI 层

当前 `PrepareOverlayAssetsAsync(...)` 依赖：

- `TranscodeJob`
- 字幕轨选择
- 原生字幕分析
- 弹幕准备 service
- GUI 当前设置

特别是 `DanmakuPreparationService` 目前直接吃 `TranscodeJob`，而不是纯数据对象。

因此当前主队列的结构是：

- GUI 负责构造 `TranscodeTaskSpec`
- GUI 通过委托把叠加准备逻辑注入给 workflow
- workflow 负责其余主链路

这是一种显式的“分步迁移”策略。

## 10. 关键文件清单

下面列出本轮架构演进里最关键的文件。

### 10.1 组合根与入口

- `Composition/AppCompositionRoot.cs`
- `AnimeTranscoder.Cli/Program.cs`

### 10.2 Core workflow

- `Workflows/AudioProcessingWorkflow.cs`
- `Workflows/ProjectAudioWorkflow.cs`
- `Workflows/TranscodeQueueWorkflow.cs`

### 10.3 共享模型

- `Models/AnimeProjectFile.cs`
- `Models/TranscriptDocument.cs`
- `Models/TranscriptSegment.cs`
- `Models/SelectionDocument.cs`
- `Models/SelectionTargetSegment.cs`
- `Models/SelectionAction.cs`
- `Models/WorkflowProgress.cs`
- `Models/TranscodeTaskSpec.cs`
- `Models/TranscodeOverlayPreparationResult.cs`
- `Models/TranscodeTaskResult.cs`
- `Models/TranscodeQueueExecutionResult.cs`

### 10.4 GUI 接入

- `ViewModels/MainViewModel.cs`
- `ViewModels/MainViewModel.AudioProject.cs`
- `ViewModels/MainViewModel.QueueWorkflow.cs`
- `Views/MainWindow.xaml`
- `Views/MainWindow.xaml.cs`

### 10.5 测试

- `AnimeTranscoder.Tests/ProjectFileServiceTests.cs`
- `AnimeTranscoder.Tests/SelectionDocumentServiceTests.cs`
- `AnimeTranscoder.Tests/TranscodeQueueWorkflowTests.cs`

## 11. 已完成验证

截至当前，已经做过以下验证。

### 11.1 构建验证

已通过：

- `dotnet build AnimeTranscoder.slnx`

### 11.2 测试验证

已通过：

- `dotnet test AnimeTranscoder.slnx`

当前测试总数：

- `16`

### 11.3 CLI smoke test

已经用真实双音轨样本跑通过：

- `probe`
- `project init`
- `audio export-work`
- `transcript import`
- `selection import`
- `audio render-selection`

### 11.4 主队列单元测试

新增 `TranscodeQueueWorkflowTests`，覆盖：

- 输入文件缺失时失败
- 输出已存在且校验通过时跳过
- 正常成功完成并按配置删除源文件
- 转码后收到取消信号时标记当前任务为 `Cancelled`

## 12. 当前仍然未完成的部分

虽然共享 workflow 基础已经成型，但距离“最初的大目标完全完成”还差几个关键步骤。

### 12.1 还没有接入本地语音识别适配层

目前已经定义好了 project/transcript/selection 流程，但还没有正式实现：

- `whisper.cpp` 导入适配
- `faster-whisper` 导入适配
- transcript 自动导入命令

也就是说，现在 transcript 是可导入的，但还没有把“本地转写工具输出 -> 我们的 transcript 协议”这层封装成正式产品能力。

### 12.2 还没有接入说话人/声源分离能力

最初希望做的“保留游戏对白、剔除主播声音”，真正的难点是：

- 不只是文本选择
- 而是声音来源本身的可分离性

当前已完成的是：

- 项目协议
- transcript / selection 外部协作接口
- 选择结果渲染

但还没有接：

- `Demucs`
- `pyannote.audio`
- 或其他本地分离工具

### 12.3 主队列的叠加准备仍未完全进入 Core

这是当前主转码迁移保留的最大技术债之一。

目前状态是：

- 主链路大部分已在 `Core`
- 叠加准备仍由 GUI 注入

这意味着当前架构已经大幅优于最初状态，但还不算“主队列完全纯 workflow 化”。

### 12.4 还没有做完整人工 GUI 回归

已经做了：

- 编译验证
- 单元测试
- CLI smoke

但还没有手工完整点击一轮 WPF 主界面的主队列流程。因此当前不能声称“GUI 层已完成完整人工验收”。

## 13. 当前架构对最初目标的支持程度

现在回头看最初目标，可以明确判断当前已经完成了什么，离目标还有多远。

### 13.1 已经完成的部分

关于“大前提：让软件可被命令行稳定驱动”，现在已经基本成立：

- 有正式 `CLI`
- 有共享 `Core`
- 有显式协议
- GUI 和 CLI 共用工作流
- 音频项目链路已能被外部 AI 间接驱动

关于“外部 AI 读 transcript 决策，软件负责执行”，现在也已经具备基础条件：

- transcript 可导入
- selection 可导入
- 软件可据 selection 进行渲染

### 13.2 仍未闭环的部分

离“从直播视频里只保留游戏人物对白”的最终目标，还差：

1. 本地转写工具适配
2. transcript 自动进入项目
3. 说话人 / 声源分离能力接入
4. 更高质量的音频筛选策略

所以当前状态可以准确描述为：

> 已经完成了“命令行可驱动 + 协议化 + GUI/CLI 共享核心流程 + 音频项目闭环 + 主转码队列共享 workflow 化”的底座建设，但最终的对白筛选能力仍需要在此基础上继续扩展。

## 14. 推荐的下一步

如果继续推进，最合理的顺序不是立即做更多 GUI，而是按下面顺序推进：

### 14.1 先做一次真实 GUI 回归

重点验证：

- 主转码队列新 workflow 路径
- 取消
- 跳过
- 失败后继续
- 弹幕/字幕叠加

因为主队列已经切到共享 workflow，这是当前最高优先级的稳定性验证。

### 14.2 再决定是否继续把叠加准备下沉到 Core

如果 GUI 回归稳定，可以进入下一轮重构：

- 把 `PrepareOverlayAssetsAsync` 需要的输入参数继续纯化
- 逐步让 `DanmakuPreparationService` 摆脱对 `TranscodeJob` 的依赖
- 最终让主队列完全摆脱 GUI 特有对象

### 14.3 在音频项目链路上接本地转写工具

这是最接近最初业务目标的一步，优先建议：

- 兼容 `whisper.cpp`
- 或兼容 `faster-whisper`

做法是增加一层适配：

- 读取本地转写工具输出
- 映射到 `TranscriptDocument`
- 直接写入 `transcript.json`
- 再复用现有 `project/transcript/selection/render` 流程

### 14.4 之后再考虑声音分离

最后再评估是否接：

- `Demucs`
- `pyannote.audio`

因为这一步是音频质量最难的部分，不应该反过来决定前面所有基础协议。

## 15. 一句话总结

这轮改造已经把 AnimeTranscoder 从“一个主要靠 GUI 驱动的 WPF 转码工具”，推进成了“GUI + CLI 共用 Core workflow、具备项目协议、可被外部 AI 协作驱动的媒体处理应用底座”。

这正是最初目标里“大前提先成立”的那部分，而且现在已经不是纸面评估，而是已经有实际代码、命令入口、GUI 接入和测试验证支撑的实现状态。
