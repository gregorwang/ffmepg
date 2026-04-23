# Ghost of Yotei Phase B 现状与 Claude 咨询提纲

本文档用于把当前 `Phase B` 的实际情况、已有产物、失败模式和待决策问题完整交给另一个模型，例如 `Claude`，避免它脱离事实空谈。

## 1. 当前目标

目标不是重新做 `OCR`，而是把已经得到的：

- 英文 `OCR`
- 中文 `OCR`

做成以英文为主轴的双语对齐结果。

当前数据结构：

- 英文侧：`4` 个 `part` 的英文硬字幕 `OCR`
- 中文侧：`13` 个切片视频的中文硬字幕 `OCR`

最终想要的是：

- 以英文时间轴为主
- 给每条英文段挂上对应中文
- 能产出机器可读 `JSON`

## 2. 已经完成的前置工作

### 2.1 中文 OCR

中文 `Phase A` 已完成，产物目录：

- `C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea`

每个中文切片目录下都有：

- `raw.srt`
- `raw.json`
- `cleaned.srt`
- `cleaned.json`

中文 `OCR` 是走 `GPU` 跑的，`Phase A` 已经人工抽检通过后冻结。

### 2.2 英文 OCR

英文 `OCR` 也已完成，产物目录：

- [english_ocr_4parts_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/english_ocr_4parts_v1)

每个 `part` 下都有：

- `cleaned.json`
- `cleaned.srt`
- `raw json/srt`
- `extraction_report.json`

当前判断：英文 `OCR` 比原来那批 `Whisper` 文本更适合作为英文主源。

## 3. 为什么不用原来的英文 Whisper 做主轴

原因不是“Whisper 完全不能用”，而是它本质上是：

- `ASR`
- `VAD` 切分
- 机器听写

所以存在这些问题：

- 文本听错
- 大量短碎片
- 重复和重叠段多
- 专有名词和人名不稳定

这个问题在 `part03` 特别明显。

因此当前路线已经改成：

- 英文主源：英文硬字幕 `OCR`
- 中文来源：中文硬字幕 `OCR`

也就是两边都基于画面字幕，而不是一边 `OCR` 一边 `ASR`。

## 4. 当前 Phase B 做过哪些尝试

### 4.1 全局语义匹配

做过多版全局语义对齐，包括：

- `phase_b_semantic_v2`
- `phase_b_semantic_v3`
- `phase_b_semantic_v4`
- `phase_b_sequence_mpnet_v1`
- `phase_b_sequence_mpnet_v2`
- `phase_b_sequence_mpnet_v3`
- `phase_b_sequence_mpnet_v4`

其中实际较有参考价值的是：

- [phase_b_sequence_mpnet_v2/bilingual_alignment.sequence.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_sequence_mpnet_v2/bilingual_alignment.sequence.json)
- [phase_b_sequence_mpnet_v4/bilingual_alignment.sequence.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_sequence_mpnet_v4/bilingual_alignment.sequence.json)

这几版的主要做法包括：

- 多语言 `embedding`
- 英文说话人前缀剥离
- 中英文本噪声过滤
- 单调顺序约束
- `speaker compatibility` 过滤
- 局部时间/进度约束

### 4.2 混合高置信候选

为了避免全量结果太脏，当前先做了一版“只保留最稳候选”的混合文件：

- [phase_b_bilingual_hybrid_highconf_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_bilingual_hybrid_highconf_v1.json)
- [phase_b_bilingual_hybrid_highconf_v1.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_bilingual_hybrid_highconf_v1.tsv)

这版的选取策略是：

- `part01` 取 `phase_b_sequence_mpnet_v2`，阈值 `>= 0.80`
- `part02` 取 `phase_b_sequence_mpnet_v4`，阈值 `>= 0.78`
- `part03` 不保留
- `part04` 取 `phase_b_sequence_mpnet_v2`，阈值 `>= 0.80`

统计：

- `part01`: `9`
- `part02`: `11`
- `part03`: `0`
- `part04`: `2`

总计 `22` 条。

### 4.3 锚点局部扩展

在上面 `22` 条锚点的基础上，又做了只围绕锚点前后小窗口扩展的版本：

- [phase_b_anchor_expansion_v2.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_anchor_expansion_v2.json)
- [phase_b_anchor_expansion_v2.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_anchor_expansion_v2.tsv)

对应脚本：

- [build_phase_b_hybrid_highconf.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_hybrid_highconf.py)
- [build_phase_b_anchor_expansion.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_anchor_expansion.py)
- [phase_b_sequence_align.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/phase_b_sequence_align.py)
- [phase_b_semantic_align.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/phase_b_semantic_align.py)

`phase_b_anchor_expansion_v2` 当前统计：

- `part01`: `22`
  - `9` 条锚点
  - `13` 条局部扩展
- `part02`: `25`
  - `11` 条锚点
  - `14` 条局部扩展
- `part04`: `5`
  - `2` 条锚点
  - `3` 条局部扩展

`part03` 当前仍没有可靠结果。

## 5. 当前最大的客观问题

### 5.1 不是没有对上，而是“对上的多是局部锚点”

当前结果不是完全无效。

已经能稳定对上一批局部高置信条目，尤其：

- `part01`
- `part02`

但这些结果还不够连续，不能直接当完整成品。

### 5.2 漏译问题非常严重

当前很多 `blk_xxxx` 是英文多句合并块，但中文只挂上了其中一句，导致：

- 整句漏掉后半段
- 多句英文只保留一句中文
- 只能算局部命中，不能算完整对齐

### 5.3 串位问题仍然存在

主要表现为：

- 上一句中文被复制到下一句
- 当前英文块对到了邻近但错误的中文句
- 连续块之间边界错位

### 5.4 说话人和 OCR 噪声问题

主要包括：

- 中文说话人字形识别错
- 地点/UI 前缀残留
- 尾部标记残缺

## 6. 人工复核后明确有问题的重点 ID

以下这些条目已经被人工判断为“明显有问题，应该优先返修”：

- `blk_0193`
- `blk_0194`
- `blk_0195`
- `blk_0196`
- `blk_0236`
- `blk_0237`
- `blk_0239`
- `blk_0240`
- `blk_0241`
- `blk_0242`
- `cue_00459`
- `blk_0470`
- `blk_0473`
- `blk_0491`
- `blk_0493`
- `blk_0514`
- `blk_0520`
- `blk_0521`
- `blk_0523`
- `blk_0544`
- `blk_0546`
- `blk_0547`
- `blk_0548`
- `blk_0470(part04)`
- `blk_0471(part04)`

这些问题不是统一一种类型，而是混合了：

- 漏译
- 串位
- 只对上局部
- 角色前缀错误
- OCR 脏字

## 7. 人工复核中已经明确指出的具体例子

以下例子是当前最有代表性的失败模式：

### 7.1 整句漏掉后半句 / 只译了第一句

- `blk_0193`
  - 英文有三句：
    - `Now, stand back—and be ready.`
    - `For what?`
    - `You'll see.`
  - 中文只剩：
    - `好了，退后，准备好。`

- `blk_0194`
  - 英文有：
    - `They're fine.`
    - `Savour the feeling.`
    - `It won't last.`
  - 中文只剩：
    - `没问题`

- `blk_0236`
  - 英文讲：
    - `斋藤是兵器高手`
    - `如果他用枪，就用双刀的速度去对付`
  - 中文只译出前半句

- `blk_0241`
  - 英文前半是：
    - `这酒你怎么运上来的？`
  - 中文只剩后半句：
    - `斋藤送了不少人`

- `blk_0242`
  - 英文后半：
    - `他去哪都会找到我，至少在这里我占优势`
  - 中文没有完整对应

- `blk_0493`
  - 英文是三句
  - 中文只保留第一句：
    - `他除了跳下悬崖无处可逃`

- `blk_0514`
  - 英文一长串对话
  - 中文只留了疯五郎第一句

- `blk_0520`
- `blk_0521`
- `blk_0523`
- `blk_0546`
- `blk_0547`
- `blk_0548`
  - 都有类似问题

### 7.2 明显串位 / 上一句中文复制到下一句

- `blk_0195`
  - 英文后半已经换成：
    - `By throwing more coals at me?`
    - `By cutting through this.`
  - 中文却仍在重复：
    - `使其与右臂一样强壮迅捷`

- `blk_0196`
  - 英文是：
    - `Left arm only. Let's see what you can do.`
  - 中文却还是上一句：
    - `使其与右臂一样强壮迅捷`

- `blk_0240`
  - 英文已经变成：
    - `That's it.`
    - `Two swords will make short work of spearmen.`
    - `Come. We will toast to the end of your training.`
  - 中文却仍是上一句：
    - `倘若敌人用枪呢？`

- `blk_0470`
- `blk_0473`
  - 中文内容与英文内容明显不在同一句上

### 7.3 说话人不齐 / 标记有误

- `cue_00459`
  - 英文：`Atsu:`
  - 中文：`笠·那就热烈欢迎一下吧`
  - 这里 `笠` 明显是 `笃` 的 OCR 错误

- `blk_0544`
  - 英文：
    - `Atsu: (Straining) You've been eating too much salmon.`
    - `Jubei: It's muscle.`
  - 中文：
    - `（吃力）你吃太多鲑鱼了。 笃：`
  - 后半说话人明显断裂

- `cue_01025`
  - 中文前缀：
    - `妖怪巢穴`
  - 这和英文：
    - `The shrine is at the top of this mountain.`
  - 不对应

## 8. 当前团队判断

### 8.1 现在的问题不再是 OCR 主体质量

当前更大的问题不是：

- 中文 OCR 完全不可用
- 英文 OCR 完全不可用

而是：

- 英文块和中文块的切分粒度不同
- 块内包含多句对话
- 一旦只挂上一句中文，就会表现成漏译
- 一旦邻域搜索范围稍微偏一点，就会发生串位

### 8.2 “只靠 embedding 再拧参数”收益已经变低

目前已经尝试过：

- 不同语义模型
- 更严格阈值
- 说话人兼容约束
- 局部窗口单调扩展

这些都能改善一部分，但还不足以解决“多句英文块对单句中文”这个核心结构问题。

### 8.3 当前最可能需要换的不是 OCR，而是对齐单元

很可能需要考虑这些方向之一：

- 把英文 `block` 再拆细
- 把中文按邻域做小范围合并
- 允许一对多 / 多对一对齐
- 不再只追求一句英文对应一句中文

## 9. 希望 Claude 优先回答的问题

请 Claude 不要泛泛地说“可以继续优化”，而是直接回答下面这些判断题。

### 问题 1

基于当前现象，主问题更像是：

- `A. clip -> part` 定位仍然不准
- `B. 英文 block 粒度过粗`
- `C. 中文 cue 粒度过碎`
- `D. 语义模型本身不够强`
- `E. 以上多个同时存在`

请它明确给排序，不要只说“都有影响”。

### 问题 2

对于这些已经明显出现漏译的 `blk_xxxx`，最合理的下一步应不应该是：

- 先把英文 `block` 拆回更细粒度，再重对

还是：

- 保留英文 `block`，改成一对多挂中文字幕

请 Claude 明确给出优先路线，并说明为什么。

### 问题 3

当前这批问题里，最值得投入的改进方向是哪一个：

- 方向 A：更强的跨语言语义模型
- 方向 B：翻译辅助再对齐
- 方向 C：块粒度重建
- 方向 D：人工锚点 + 邻域扩散
- 方向 E：图模型 / DTW / HMM 类序列方法

请 Claude 给出排序，不要平均用力。

### 问题 4

如果目标是尽快做出“可交付的局部连续双语段”，而不是完美的全量成品，那么当前应该：

- 继续扩 `part01/part02`
- 还是先单独攻克 `part03`

请明确建议。

### 问题 5

对下面这些问题行：

- `blk_0193`
- `blk_0194`
- `blk_0195`
- `blk_0196`
- `blk_0236`
- `blk_0237`
- `blk_0239`
- `blk_0240`
- `blk_0241`
- `blk_0242`
- `blk_0493`
- `blk_0514`
- `blk_0520`
- `blk_0521`
- `blk_0523`
- `blk_0546`
- `blk_0547`
- `blk_0548`

请 Claude 判断：这些更像是“对齐单元设计错误”，还是“邻域搜索范围错误”。

## 10. 建议 Claude 优先看的文件

如果 Claude 只看少量文件，建议优先看这些：

- [phase_b_anchor_expansion_v2.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_anchor_expansion_v2.tsv)
- [phase_b_anchor_expansion_v2.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_anchor_expansion_v2.json)
- [phase_b_bilingual_hybrid_highconf_v1.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_bilingual_hybrid_highconf_v1.tsv)
- [phase_b_sequence_mpnet_v2/bilingual_alignment.sequence.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_sequence_mpnet_v2/bilingual_alignment.sequence.json)
- [phase_b_sequence_mpnet_v4/bilingual_alignment.sequence.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_sequence_mpnet_v4/bilingual_alignment.sequence.json)
- [phase_b_sequence_align.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/phase_b_sequence_align.py)
- [build_phase_b_hybrid_highconf.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_hybrid_highconf.py)
- [build_phase_b_anchor_expansion.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_anchor_expansion.py)

## 11. 当前主结论

当前项目已经不是“完全没有成果”，而是：

- 英文和中文 `OCR` 都已成形
- 局部高置信锚点已经有了
- 局部扩展也有一版能看

真正卡住的是：

- 如何把“局部能对上的句子”变成“连续且不漏句的双语段”

也就是说，`Phase B` 的核心问题现在更像：

- 对齐单元设计
- 一对多 / 多对一挂载策略
- 块内多句处理

而不再主要是：

- OCR 不行
- GPU 不行
- 语义模型完全没效果

## 12. 可直接复制给 Claude 的增强版提问稿

下面这一整段文本是给网页端 `Claude` 用的，不依赖它访问本地文件。可以整段复制到对话框里。

```text
我在做一个“中英双语字幕对齐”的项目，想请你基于下面我提供的完整上下文，帮我判断问题根因，并给出下一步最合理的技术方案。请注意：你不能访问我的本地文件，所以你只能基于我下面贴给你的事实、统计、例子和失败样本来分析。请不要泛泛而谈，我需要你明确排序、明确取舍、明确建议。

====================
1. 项目目标
====================

目标是把一批视频里的英文硬字幕和中文字幕对齐，最终得到“以英文为主轴的双语 JSON”。

更具体地说：

- 英文作为主时间轴
- 每条英文段落挂一个对应的中文结果
- 最终输出是机器可读 JSON
- 如果没有足够靠谱的中文匹配，可以留空，但不要强配

====================
2. 数据结构
====================

当前手头的数据不是同一种结构：

英文侧：
- 来自 4 个长视频 part（part01, part02, part03, part04）
- 这些 part 里有英文硬字幕
- 我已经对这 4 个 part 跑过英文 OCR，拿到了英文 cleaned JSON / SRT

中文侧：
- 来自 13 个切出来的中文视频片段
- 每个片段也有中文硬字幕
- 我已经对这 13 个中文视频跑过中文 OCR，拿到了中文 cleaned JSON / SRT

所以当前不是“同一个视频里两条字幕轨直接对齐”，而是：
- 英文：4 个长时间线
- 中文：13 个切片时间线

最终要做的是：
- 先把这 13 个中文切片挂回 4 个英文 part 的时间结构里
- 再以英文字幕为主，把中文字幕挂上去

====================
3. OCR 现状
====================

中文 OCR：
- 已经完成
- GPU 跑的
- 样本抽检基本通过
- 产出 cleaned JSON / cleaned SRT

英文 OCR：
- 最开始我尝试过用 Whisper 的英文转写做英文主源
- 后来发现 Whisper 文本噪声很重、重复多、切分碎、专有名词不稳定
- 所以改成了“直接 OCR 读画面上的英文硬字幕”
- 当前判断：英文 OCR 明显比原始 Whisper 结果更适合作为英文主源

也就是说，我现在做的是：
- 英文：英文硬字幕 OCR
- 中文：中文硬字幕 OCR

这两边的数据源层级是统一的，都是 OCR 读画面字幕，而不是一边 OCR 一边 ASR。

====================
4. 已做过的主要尝试
====================

我已经做过多轮对齐尝试，不是从零开始。下面是我真实尝试过的方向：

1. 全局跨语言语义匹配
- 多语言 embedding
- 单调顺序约束
- 时间/进度约束
- 说话人兼容过滤
- 中英文本噪声过滤

2. 不同版本的 sequence alignment
我做过多版，当前最有参考价值的是：
- 一个叫 v2 的版本
- 一个叫 v4 的版本

这两版的差异大致是：
- v2：part01 效果相对更好
- v4：part02 明显比 v2 更好，因为它引入了更强的 speaker compatibility 过滤
- part03 和 part04 仍然比较差

3. 混合高置信候选
我没有继续相信“全量自动结果”，而是先从不同版本里挑最稳的高置信结果，做了一版混合候选集。

这版混合候选的规则是：
- part01 取 v2，阈值 >= 0.80
- part02 取 v4，阈值 >= 0.78
- part03 暂时不留
- part04 取 v2，阈值 >= 0.80

得到的高置信候选条数：
- part01: 9
- part02: 11
- part03: 0
- part04: 2
- 总计：22 条

4. 锚点局部扩展
我没有拿这 22 条当成最终结果，而是把它们当“可靠锚点”，然后只在锚点前后小窗口里做局部扩展，避免继续全局乱搜。

局部扩展之后得到：
- part01: 22 条
  - 其中 9 条原始锚点
  - 13 条局部扩展
- part02: 25 条
  - 其中 11 条原始锚点
  - 14 条局部扩展
- part04: 5 条
  - 其中 2 条原始锚点
  - 3 条局部扩展
- part03: 仍然 0 条可靠结果

结论是：
- part01 和 part02 已经开始形成“局部连续双语段”
- part04 只有少量可用
- part03 还是明显掉队

====================
5. 当前最核心的问题
====================

现在的问题不是“完全没有对上”，而是：

- 局部已经能对上一批高置信句子
- 但一旦扩展成连续段，就会暴露出：
  - 漏译
  - 串位
  - 一对多 / 多对一没处理好
  - 说话人前缀和 OCR 噪声残留
  - 英文 block 粒度太粗时，中文只挂上其中一句

所以我怀疑当前真正的核心问题，可能已经不是 OCR 质量，也不是单纯 embedding 不够强，而是：
- 对齐单元设计有问题
- 英文 block 太粗
- 中文 cue 粒度和英文 block 不匹配
- 缺少一对多 / 多对一挂载策略

====================
6. 关键统计
====================

当前一些比较重要的事实和统计如下：

1. 混合高置信候选集只保留下来 22 条
- part01: 9
- part02: 11
- part03: 0
- part04: 2

2. 锚点扩展后为：
- part01: 22
- part02: 25
- part04: 5

3. 当前高置信结果并不是“均匀覆盖所有片段”，而是集中在少数 source clip：
- part01 的可靠结果集中在 1 个中文片段
- part02 的可靠结果集中在 1 个中文片段
- part04 的可靠结果集中在 1 个中文片段
- part03 没有可靠结果

4. 这意味着当前方法更像是在找到“局部可靠锚点”，而不是已经建立了完整双语时间轴。

====================
7. 典型失败模式
====================

下面是我已经人工检查出来的典型失败模式。

--------------------------------
7.1 整句漏掉后半句 / 只译了第一句
--------------------------------

例子 1：
ID: blk_0193

英文：
- Now, stand back—and be ready.
- For what?
- You'll see.

中文当前只有：
- 好了，退后，准备好。

问题：
- 后两句完全漏掉

例子 2：
ID: blk_0194

英文：
- They're fine.
- Savour the feeling.
- It won't last.

中文当前只有：
- 没问题

问题：
- 只对上了第一句，后两句都没了

例子 3：
ID: blk_0236

英文大意：
- 斋藤是兵器高手
- 如果他用枪，就用双刀的速度应对

中文当前只保留了前半句

例子 4：
ID: blk_0241

英文前半是：
- 这酒你怎么运上来的？

中文当前却只剩后半句：
- 斋藤送了不少人

例子 5：
ID: blk_0242

英文后半大意：
- 他去哪都会找到我
- 至少在这里我占优势

中文没有完整对应

例子 6：
ID: blk_0493

英文有三句，中文只剩：
- 他除了跳下悬崖无处可逃

例子 7：
ID: blk_0514

英文是一整串对白，中文只保留了疯五郎第一句

类似问题还出现在：
- blk_0520
- blk_0521
- blk_0523
- blk_0546
- blk_0547
- blk_0548

--------------------------------
7.2 明显串位 / 上一句中文复制到下一句
--------------------------------

例子 1：
ID: blk_0195

英文后半已经变成：
- By throwing more coals at me?
- By cutting through this.

中文却还在重复上一句的意思：
- 使其与右臂一样强壮迅捷

例子 2：
ID: blk_0196

英文：
- Left arm only.
- Let's see what you can do.

中文还是上一句那句：
- 使其与右臂一样强壮迅捷

例子 3：
ID: blk_0240

英文已经变成：
- That's it.
- Two swords will make short work of spearmen.
- Come. We will toast to the end of your training.

中文却还是上一句的问题句：
- 倘若敌人用枪呢？

例子 4：
ID: blk_0470

例子 5：
ID: blk_0473

这两条中文和英文内容也明显不像在同一句上，更像从邻近句串过来的。

--------------------------------
7.3 说话人前缀 / OCR 脏字问题
--------------------------------

例子 1：
ID: cue_00459

英文：
- Atsu: Let's give them a warm welcome.

中文当前：
- 笠·那就热烈欢迎一下吧

这里“笠”大概率是 OCR 把“笃”识别错了。

例子 2：
ID: blk_0544

英文：
- Atsu: (Straining) You've been eating too much salmon.
- Jubei: It's muscle.

中文当前：
- （吃力）你吃太多鲑鱼了。笃：

问题：
- 后半角色标记明显断裂
- 十兵卫那句没有落下来

例子 3：
ID: cue_01025

英文：
- The shrine is at the top of this mountain.

中文前面却多出：
- 妖怪巢穴

这显然不是这句英文的对应内容，更像地点或 UI 残留。

====================
8. 我已经确认“有问题”的重点 ID
====================

下面这些条目已经被我人工判断为明显有问题，应该优先返修：

- blk_0193
- blk_0194
- blk_0195
- blk_0196
- blk_0236
- blk_0237
- blk_0239
- blk_0240
- blk_0241
- blk_0242
- cue_00459
- blk_0470
- blk_0473
- blk_0491
- blk_0493
- blk_0514
- blk_0520
- blk_0521
- blk_0523
- blk_0544
- blk_0546
- blk_0547
- blk_0548
- blk_0470(part04)
- blk_0471(part04)

====================
9. 一些当前看起来“是成功的”样本
====================

不是所有东西都错了，当前有些局部锚点看起来是明显对的。这部分很重要，因为它说明整个方向不是完全错误，而是“局部已对上，但连续扩展不稳”。

一些较像样的样本：

1.
英文：
- Hanbei: There's an old training sword over there.
中文：
- 半兵卫：那儿有把旧的训练刀，捡起来。

2.
英文：
- Hanbei: Your left arm's getting stronger.
中文：
- 半兵卫：左臂更强壮了。

3.
英文：
- Jubei: No one can take that from us.
中文：
- 十兵卫：没有人能改变这一点

4.
英文：
- Atsu: Take my hand.
中文：
- 笃：抓我的手。

5.
英文：
- Atsu: We don't have to talk about him.
中文：
- 不想提他也没关系。

所以问题不是“整个语义匹配完全无效”，而是：
- 能找到一批高置信锚点
- 但围绕锚点向前后扩展时，很快暴露出 block 粒度和挂载方式的问题

====================
10. 我现在最想让你判断的核心问题
====================

请你不要只说“都可能有影响”，我需要你明确给排序、明确取舍。

问题 1：
基于我上面的事实，你判断当前主问题更像下面哪几个，按优先级排序：

A. 13 个中文切片挂回 4 个英文 part 的定位仍然不够准
B. 英文 block 粒度过粗，导致一条英文 block 内含多句对白，而中文只挂上其中一句
C. 中文 cue 粒度过碎
D. 跨语言 embedding 本身不够强
E. 缺少一对多 / 多对一对齐机制
F. speaker / prefix / OCR 噪声只是次要问题，不是主因
G. 还有别的更主要原因

请你给出排序，不要平均用力。

问题 2：
像我这种情况，下一步到底更应该优先做哪条路？

路线 A：
把英文 block 重新拆细，再重做对齐

路线 B：
保留当前英文 block，但允许一个英文 block 挂多条中文，或者多条英文挂一条中文

路线 C：
先做机器翻译辅助，再做更强的语义对齐

路线 D：
先用更多人工锚点，把连续片段范围限定得更死，再在片段内局部对齐

路线 E：
换成更强的序列模型 / 图模型 / DTW / HMM 风格的方法

请你明确给出优先顺序，并说明为什么。

问题 3：
对于我上面列出来那些问题 ID，你判断它们更像是：

- 对齐单元设计错误
- 邻域搜索范围错误
- 一对多 / 多对一没处理
- OCR 文本脏，但不是主因
- 多种问题叠加

请按类型拆开分析，不要一句“都有”带过。

问题 4：
如果目标不是一口气做出完美全量双语轴，而是先尽快做出“可交付的局部连续双语段”，你建议我：

- 继续深挖 part01 / part02
- 还是先硬攻 part03
- 还是应该先停下来重构对齐单元设计，再继续所有 part

请给明确建议。

问题 5：
请你直接给一个“最值得执行的下一步技术方案”，要求具体到：

- 输入是什么
- 对齐单元是什么
- 是否允许一对多 / 多对一
- 大致的打分方式是什么
- 怎么避免漏译
- 怎么避免上一句中文串到下一句
- 怎么做人工抽检
- 怎么定义验收标准

====================
11. 我希望你顺手回答的附加问题
====================

附加问题 1：
你判断当前最大的技术方向性错误，是不是“过早把英文 OCR cue 合成 block”？

附加问题 2：
如果英文侧保留更细粒度的 cue，而不是先 merge 成 block，再在局部做一对多挂载，会不会比现在更合理？

附加问题 3：
如果不想让算法无限复杂，是否应该直接采用：
- 英文细粒度 cue
- 中文保留原 cue
- 允许局部 1:N / N:1
- 最后输出时再做展示层合并

这种设计？

附加问题 4：
针对 `blk_0193-0242` 这一段和 `blk_0493-0548` 这一段，你觉得更像是：
- 英文切块不对
- 中文挂载不对
- 还是两边都需要重新建模？

====================
12. 你回答时请按这个格式
====================

请按下面结构回答，不要跳来跳去：

1. 先给结论摘要
2. 再给问题根因排序（明确排序）
3. 再给你推荐的主路线（只选 1 条主路线，其他当备选）
4. 再解释为什么我现在会出现“漏译 + 串位 + block 内不完整”
5. 再给一个可执行的实施步骤，最好是分 3 个阶段
6. 最后给一个风险清单，说明最容易踩的坑

如果你觉得有必要，也请你顺手给我一个：
- “我下一轮应该怎么改算法”的伪代码级思路
或者
- “我下一轮怎么组织人工审核”的方案

请务必具体，不要泛泛而谈。
```

## 13. 使用建议

如果网页端上下文长度吃紧，建议只保留：

- 第 `1~5` 节背景
- 第 `7~10` 节问题和样例
- 第 `12` 节回答格式要求

如果 `Claude` 回答得还是太虚，可以继续追问它两件事：

1. “请你不要给多个平均方案，只选一个主路线，并说明为什么不选其他路线。”
2. “请你把建议进一步收敛成可以在一周内验证的最小实验设计。”
