# AnimeTranscoder 弹幕方案技术设计

更新时间：2026-04-08

## 1. 文档目标

这份文档解决三个目的：

1. 收敛当前弹幕来源模型，去掉产品层面的语义混乱。
2. 把弹幕显示区域从两档扩展成更细的离散档位。
3. 为未来“智能避脸 / 前景遮挡弹幕”预留可扩展的技术接口，但第一阶段不直接实现重型视觉分割。

本文档不是现状说明，而是后续改造的技术基线。

## 2. 当前现状与问题归纳

### 2.1 当前现状

当前项目已具备这些能力：

1. 任务级绑定本地 `xml/ass` 弹幕文件。
2. 旧链路保留了 `Bilibili 自动获取` 弹幕。
3. `xml -> ass` 转换支持：
   - 关键词屏蔽
   - 特殊类型过滤
   - 时间偏移
   - 密度控制
   - 两档区域模式
4. 支持窗口内单帧叠加预览。
5. 支持逐条禁用、搜索、批量禁用、规则导入导出。

### 2.2 当前主要问题

#### 问题 A：来源模型混乱

来源决定逻辑当前放在全局配置 `Settings.DanmakuSourceMode`，但具体文件绑定发生在任务级。

这会导致：

1. 全局模式压过任务事实。
2. 用户心智模型混乱。
3. UI 重复表达“来源”。
4. 扩展更多任务级能力时越来越别扭。

#### 问题 B：区域模式过粗

当前只有：

1. `full_screen`
2. `upper_half`

这不足以覆盖番剧场景里常见的弹幕使用偏好。

#### 问题 C：未来高级功能缺少架构预留

现在还没有为以下能力预留明确接口：

1. 人脸避让
2. 场景安全区
3. 前景遮挡弹幕
4. 多阶段分析缓存

## 3. 目标方案总览

### 3.1 第一阶段必须完成

第一阶段只做确定性、高收益改造：

1. 移除全局“弹幕来源模式”主导逻辑。
2. 改为以“任务是否绑定本地弹幕文件”为唯一主路径。
3. 将区域模式扩展为：
   - 顶部区域
   - 上方 1/5
   - 上方 1/4
   - 上方 1/3
   - 上方 1/2
   - 全屏铺开
4. 保持 XML/ASS 双格式导入。
5. 保持当前分析、过滤、规则、预览、烧录链路继续成立。

### 3.2 第二阶段建议完成

第二阶段做轻量智能增强：

1. 人脸检测
2. 人脸安全区缓存
3. 弹幕轨道避让
4. 预览中展示“避让开关”

### 3.3 第三阶段再评估

第三阶段才考虑重型能力：

1. 人像分割
2. 前景 mask
3. 弹幕夹层合成

## 4. 第一阶段方案：弹幕来源收敛

## 4.1 设计原则

来源不再是“系统帮你选哪条链路”，而是“当前任务绑定了什么输入”。

新的产品原则：

1. 用户启用弹幕，不代表系统自动去找弹幕。
2. 用户启用弹幕后，任务必须自己绑定文件，或者明确显示“未绑定弹幕文件”。
3. 一个任务只对一个弹幕输入负责。
4. 本地文件才是第一公民。
5. 任何自动获取能力都不再进入主流程。

## 4.2 UI 改造方案

### 全局配置区

保留：

1. `启用弹幕叠加`
2. `显示区域`
3. `字体名称`
4. `字号`
5. `密度`
6. `时间偏移`
7. `屏蔽词`
8. `过滤特殊弹幕`

删除：

1. `弹幕来源` 下拉
2. `映射配置` 作为主界面主字段

处理建议：

1. `映射配置` 不删除代码，但从主界面移走。
2. 如果以后还保留 Bilibili 自动链路，将其收纳到“实验功能”或“高级工具”页面。

### 任务详情区

保留并强化：

1. `绑定本地弹幕`
2. `清空绑定`
3. `打开弹幕文件`
4. `分析摘要`
5. `过滤结果`
6. `生成 ASS`
7. `手动禁用`

新增建议：

1. `弹幕格式`
   - XML
   - ASS
2. `绑定状态`
   - 未绑定
   - 已绑定 XML
   - 已绑定 ASS
3. `准备状态`
   - 待分析
   - 分析成功
   - 分析失败

## 4.3 配置模型改造

### 当前问题

`AppSettings.DanmakuSourceMode` 是全局字段，它把“来源”定义成了全局状态。

### 改造原则

第一阶段应当让“来源”从配置层退场。

### 建议数据结构

#### `AppSettings`

删除或废弃：

1. `DanmakuSourceMode`
2. `DanmakuMappingPath` 从主流程剥离，但可暂时保留以兼容旧设置文件

保留：

1. `EnableDanmaku`
2. `DanmakuAreaMode`
3. `DanmakuFontName`
4. `DanmakuFontSize`
5. `DanmakuDensity`
6. `DanmakuTimeOffsetSeconds`
7. `DanmakuBlockKeywords`
8. `DanmakuFilterSpecialTypes`

#### `TranscodeJob`

保留并作为唯一事实来源：

1. `DanmakuInputPath`
2. `DanmakuSourceSummary`
3. `DanmakuPreparationSummary`
4. `DanmakuXmlPath`
5. `DanmakuAssPath`
6. `DanmakuXmlCommentCount`
7. `DanmakuKeptCommentCount`
8. `DanmakuExcludedCommentKeys`

新增建议：

1. `DanmakuInputKind`
   - `none`
   - `xml`
   - `ass`
2. `DanmakuBindState`
   - `unbound`
   - `bound`
   - `analyzed`
   - `failed`

这样 ViewModel 和 UI 都不需要再猜。

## 4.4 服务层改造

### 目标

`DanmakuPreparationService.PrepareAsync(...)` 不再先看全局 `DanmakuSourceMode`，而是先看任务事实。

### 新逻辑

1. 如果 `EnableDanmaku == false`
   - 返回“弹幕禁用”
2. 如果 `job.DanmakuInputPath` 为空
   - 返回“未绑定本地弹幕文件”
3. 如果文件不存在
   - 返回失败
4. 如果扩展名是 `.ass`
   - 直接使用
5. 如果扩展名是 `.xml`
   - 走 XML 分析与 ASS 生成
6. 其他扩展名
   - 返回失败

### 伪代码

```csharp
if (!settings.EnableDanmaku)
{
    return Disabled();
}

if (string.IsNullOrWhiteSpace(job.DanmakuInputPath))
{
    return Fail("未绑定本地弹幕文件");
}

if (!File.Exists(job.DanmakuInputPath))
{
    return Fail("弹幕文件不存在");
}

switch (Path.GetExtension(job.DanmakuInputPath).ToLowerInvariant())
{
    case ".ass":
        return UseAss(job.DanmakuInputPath);
    case ".xml":
        return ConvertXmlToAss(job.DanmakuInputPath);
    default:
        return Fail("仅支持 xml/ass");
}
```

### 兼容策略

如果短期内不想删掉 Bilibili 代码，可以这样处理：

1. 保留相关服务类，但不在主 UI 暴露。
2. `DanmakuPreparationService` 主流程不再走 Bilibili 分支。
3. 如果要保留，可新增一个独立入口，例如：
   - `实验功能 -> 从 Bilibili 解析弹幕`

这叫“代码兼容保留，产品主路径移除”。

## 4.5 设置迁移

旧设置文件里如果仍有：

1. `DanmakuSourceMode`
2. `DanmakuMappingPath`

迁移策略：

1. 可以继续读取，但不再驱动主流程。
2. 不再把 `DanmakuSourceMode` 写回新设置文件。
3. 若用户从旧版本升级，已有任务级绑定逻辑不受影响。

## 5. 第一阶段方案：区域模式细分

## 5.1 新的区域枚举设计

建议新增离散枚举：

```csharp
public static class DanmakuAreaModes
{
    public const string TopBand = "top_band";
    public const string UpperFifth = "upper_1_5";
    public const string UpperQuarter = "upper_1_4";
    public const string UpperThird = "upper_1_3";
    public const string UpperHalf = "upper_1_2";
    public const string FullScreen = "full_screen";
}
```

说明：

1. `TopBand` 表示“顶部固定窄条区域”。
2. 其余几个枚举表示“允许弹幕占用画面上方多少比例的高度”。
3. 这样比写 `top_only` 更不歧义。

## 5.2 为什么不建议直接叫“只显示顶部”

因为“顶部”有歧义：

1. 是只保留顶部弹幕模式？
2. 还是所有弹幕都被限制到顶部区域？

工程上建议明确成“顶部窄带区域”。

## 5.3 区域计算公式

当前生成器里有：

1. `PlayResY`
2. `areaTop`
3. `areaBottom`
4. `reservedBottom`

改造后建议用统一比例函数：

```csharp
private static int ResolveAreaBottom(AppSettings settings, int playResY, int areaTop, int reservedBottom)
{
    var safeBottom = Math.Max(areaTop + 120, playResY - reservedBottom);

    return settings.DanmakuAreaMode switch
    {
        DanmakuAreaModes.TopBand => areaTop + 160,
        DanmakuAreaModes.UpperFifth => areaTop + (int)Math.Round(playResY * 0.20),
        DanmakuAreaModes.UpperQuarter => areaTop + (int)Math.Round(playResY * 0.25),
        DanmakuAreaModes.UpperThird => areaTop + (int)Math.Round(playResY * 0.333333),
        DanmakuAreaModes.UpperHalf => areaTop + (int)Math.Round(playResY * 0.50),
        _ => safeBottom
    };
}
```

然后再做边界修正：

```csharp
areaBottom = Math.Min(safeBottom, Math.Max(areaTop + minRequiredHeight, resolvedAreaBottom));
```

## 5.4 轨道数量计算

现在轨道数量是按：

1. `availableHeight / lineHeight`

得出。

这个思路可以保留。

区域缩小后，自然会导致：

1. 轨道数下降
2. 同时屏幕容纳量下降
3. 更容易触发密度削减和轨道复用

这正是预期行为。

## 5.5 顶部 / 底部 / 滚动模式在新区域中的行为

建议保持一致性：

1. 滚动弹幕：
   - 在 `areaTop ~ areaBottom` 区间内分配轨道
2. 顶部弹幕：
   - 从 `areaTop` 往下排
3. 底部弹幕：
   - 仍然从 `areaBottom` 往上排

注意这里的“底部弹幕”并不是画面底部，而是“当前弹幕可用区域的下边界”。

这点一定要明确，否则一旦选择 `upper_1_5`，底部弹幕仍跑到全片底部就会违反区域模式定义。

## 5.6 对字幕安全区的处理

当前实现已经有一个底部安全区概念：

1. 如果同时烧录内嵌字幕，则保留更大的底部安全区。
2. 否则保留较小安全区。

这个逻辑应保留，但要从“全屏模式专属”变成统一参与边界计算。

换句话说：

1. 先算字幕安全区。
2. 再算弹幕区域目标高度。
3. 最后取不冲突结果。

## 5.7 UI 文案建议

下拉项建议直接写：

1. `顶部窄带`
2. `上方 1/5`
3. `上方 1/4`
4. `上方 1/3`
5. `上方 1/2`
6. `全屏铺开`

并配一行说明：

`弹幕将限制在对应高度区域内；底部仍会自动为字幕预留安全区。`

## 6. 预览链路需要同步调整

## 6.1 当前状态

当前预览是：

1. 根据当前设置生成 ASS
2. 用 ffmpeg 在指定时间点输出单帧 PNG

这条链路是正确的，不需要推翻。

## 6.2 新增区域模式后需要保证的事

必须保证：

1. 预览使用的 ASS 与正式烧录使用的 ASS 完全同源。
2. 区域模式变化后，预览和正式输出不能出现不一致。
3. 区域模式应该进入 ASS 缓存指纹。

当前缓存指纹已经包含 `DanmakuAreaMode`，这是对的，后续扩展枚举值后可直接沿用。

## 6.3 预览增强建议

为配合新区域模式，建议在预览面板补两个信息：

1. 当前区域模式名称
2. 当前估算轨道数

这样用户在切换 `1/5 / 1/4 / 1/3 / 1/2` 时，更容易理解为什么画面上弹幕量变化了。

## 7. XML 与 ASS 的策略差异

## 7.1 XML 路径

XML 路径可以做完整预处理：

1. 屏蔽词
2. 特殊类型过滤
3. 时间偏移
4. 密度控制
5. 区域模式
6. 手动禁用规则

## 7.2 ASS 路径

当前 ASS 是直通。

这意味着：

1. 如果导入的是外部 ASS，区域模式不一定能二次生效。
2. 因为外部 ASS 本身已经固化了轨道和位置。

### 第一阶段建议

第一阶段不对外部 ASS 进行重排。

但 UI 必须明确提示：

1. `XML 支持完整过滤与区域重排`
2. `ASS 将按原样烧录，仅参与总叠加`

否则用户会误以为自己切了 `1/5`，外部 ASS 也会自动改位，这会导致认知错误。

## 8. 测试设计

## 8.1 来源模型测试

应覆盖：

1. `EnableDanmaku=false` 时直接跳过。
2. `EnableDanmaku=true` 但未绑定文件时失败。
3. 绑定 `.xml` 时成功生成 ASS。
4. 绑定 `.ass` 时直通成功。
5. 绑定不存在文件时失败。
6. 绑定非法扩展名时失败。

## 8.2 区域模式测试

至少要覆盖：

1. `TopBand`
2. `UpperFifth`
3. `UpperQuarter`
4. `UpperThird`
5. `UpperHalf`
6. `FullScreen`

验证点：

1. 生成 ASS 成功。
2. 对话行的 `y` 不超出目标区域。
3. 底部模式也不越界到目标区域外。
4. 烧录字幕时仍保留安全区。

## 8.3 预览一致性测试

验证：

1. 同一输入、同一时间点、同一设置下，预览帧和正式生成 ASS 的过滤参数一致。
2. 切换区域模式会改变缓存键。

## 8.4 回归测试

验证：

1. 字幕和弹幕同时烧录不回退。
2. 规则导入导出不受影响。
3. 手动禁用仍生效。
4. 关键词批量禁用仍生效。

## 9. 第二阶段预留：人脸安全区避让

## 9.1 目标定义

第二阶段不做“人物图层盖住弹幕”，只做“避免挡脸”。

这是一种更轻、更现实的智能弹幕。

## 9.2 技术路线

流程建议：

1. 对视频做抽帧或逐帧检测。
2. 检测人脸框。
3. 将结果按时间写入缓存。
4. 弹幕排布时查询对应时间点的人脸禁入区域。
5. 轨道分配时跳过重叠轨道。

## 9.3 数据结构建议

新增模型：

```csharp
public sealed class FaceAvoidanceFrame
{
    public double TimeSeconds { get; init; }
    public List<RectF> FaceBoxes { get; init; } = [];
}
```

新增任务缓存：

```csharp
public sealed class DanmakuSceneAnalysisCache
{
    public string VideoPath { get; init; } = string.Empty;
    public List<FaceAvoidanceFrame> Frames { get; init; } = [];
}
```

## 9.4 与现有生成器的结合方式

在 `BuildAssDocument(...)` 中，当前的轨道分配是纯时间维度。

未来要扩展成：

1. 时间维度
2. 纵向轨道占用
3. 人脸区域碰撞检测

可抽象出一个新组件：

```csharp
public interface IDanmakuLanePlanner
{
    LanePlacement Plan(DanmakuComment comment, DanmakuLayoutContext context);
}
```

第一阶段保持默认实现。
第二阶段增加 `FaceAwareDanmakuLanePlanner`。

这样不会把复杂逻辑直接堆进 `DanmakuAssGeneratorService`。

## 10. 第三阶段预留：前景遮挡弹幕

## 10.1 目标定义

第三阶段才实现真正意义上的：

1. 人物在上层
2. 弹幕在中间层
3. 背景在下层

## 10.2 正确认知

这不是简单的 ASS 参数升级，而是一次“视频分层合成能力”升级。

## 10.3 推荐总体架构

### 阶段 1：前景分析

使用外部视觉模型得到每帧或关键帧的：

1. 人像 mask
2. 或主体 mask

### 阶段 2：mask 平滑与缓存

需要处理：

1. 帧间抖动
2. 边界毛刺
3. 关键帧插值

### 阶段 3：合成

理论合成顺序：

1. 原视频 -> 背景层
2. ASS 弹幕叠加到背景层
3. 前景 mask 对应的人物层叠回最上层

## 10.4 ffmpeg 在这里的位置

ffmpeg 在这个方案里负责的是：

1. 解码视频
2. 叠加 ASS
3. 叠加前景层
4. 输出编码

它不负责：

1. 识别人物
2. 生成 mask
3. 理解语义前景

## 10.5 为什么不建议直接在当前版本开做

因为它至少会带来以下新模块：

1. 模型推理引擎
2. 分析缓存格式
3. 关键帧对齐
4. 预览时的双层或三层合成
5. 性能与中间文件管理

这已经是中型特性，不应和第一阶段来源收敛、区域细分混在一起做。

## 11. 实施顺序建议

## 第一批

1. 删掉全局“弹幕来源”下拉。
2. 主流程只认任务级本地绑定文件。
3. 区域模式扩成 6 档。
4. 补 UI 提示：XML 与 ASS 的处理差异。
5. 补测试。

## 第二批

1. 预览面板展示轨道数和区域说明。
2. 如果需要，再给区域模式配缩略示意图。
3. 做人脸避让原型验证。

## 第三批

1. 评估是否值得上前景分割。
2. 如果做，单独开模块，不与第一阶段代码混改。

## 12. 风险与边界

### 风险 1：外部 ASS 无法完全重排

这个必须在产品层说清楚。

### 风险 2：区域越小，密度感知越强

用户可能误以为弹幕“被吞了”，实际上是空间变小导致轨道复用与密度筛减更明显。

### 风险 3：人脸避让和前景遮挡不是一回事

文档、UI、后续需求沟通里必须分开讲，否则容易承诺过头。

## 13. 最终结论

后续改造的正确方向应当是：

1. 把弹幕主路径收敛成“任务级手动导入文件”。
2. 将区域控制升级为多档位高度限制。
3. 把“智能弹幕”拆成两个阶段能力：
   - 人脸避让
   - 前景遮挡
4. 第一阶段先解决确定性、高收益问题，不直接进入重型视觉分割。

这样改，产品语义会干净，技术链路也更稳，后面继续做智能化时不会推翻现有实现。
