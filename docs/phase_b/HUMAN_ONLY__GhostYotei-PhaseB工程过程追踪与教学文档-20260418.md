# GhostYotei Phase B 工程过程追踪与教学文档

本文档不是结果汇报，而是工程过程复盘。目标是把这次 `Phase B` 中英双语字幕对齐工作，拆成一份可以学习工程思维、排错方法、路线修正方式的过程记录。

它重点回答 5 个问题：

1. 我们一开始到底在解什么问题。
2. 为什么最开始的方法不够好。
3. 中间做了哪些实验，分别得到什么结果。
4. 为什么最后路线会切到 `cue-level + 局部窗口 + 1:N/N:1`。
5. 这个过程里有哪些工程习惯值得保留。

---

## 1. 问题定义

### 1.1 最终目标

目标不是单纯拿到 `SRT`，而是得到：

- 以英文为主轴的双语对齐结果
- 机器可读的 `JSON`
- 英文字幕为主，中文字幕作为挂载字段

理想结构类似：

```json
{
  "part": "part02",
  "segments": [
    {
      "start": 6255.0,
      "end": 6257.0,
      "english_text": "Atsu: Missing your new friend?",
      "chinese_text": "笃：想念你的新朋友了？"
    }
  ]
}
```

### 1.2 数据现实

这个任务麻烦的地方，不在“字幕语言不同”，而在“数据结构不同”：

- 英文侧：`4` 个 `part`
- 中文侧：`13` 个切片视频

所以不是“同一条时间线上的两条字幕轨对齐”，而是：

- 先把 `13` 个中文片段挂回 `4` 个英文 `part`
- 再做英文主轴对齐

这是整个工程里第一个关键认识。

如果一开始把它误解成“普通双语字幕配对”，后面的路线就容易跑偏。

---

## 2. 为什么不直接用 Whisper 英文稿

### 2.1 初始直觉

最开始很自然会想到：

- 英文已经有 `Whisper` 转写结果
- 那就直接拿 `Whisper transcript` 当英文主轴

这个思路看起来省事，但很快暴露出结构问题。

### 2.2 Whisper 的实际问题

`Whisper + VAD` 产物本质上是：

- 自动听写
- 自动切句
- 自动重叠/截断

它不是人工校对过的正式英文字幕。

实际观察到的问题包括：

- 文本听错
- 人名、专名不稳定
- 切分很碎
- 重复段很多
- 相邻段高度重叠

这意味着如果中文是“画面硬字幕 OCR”，英文却是“语音自动转写”，两边的数据源层级不一致。

工程上这是一个很危险的信号：

- 不是不能对
- 但对齐上限会被英文主源限制住

### 2.3 路线修正

因此路线调整为：

- 中文：从视频硬字幕做 OCR
- 英文：也从视频硬字幕做 OCR

这样两边的输入源统一成“读画面上的字”，不是一边读画面、一边听音频。

这是 `Phase B` 的第一轮重要路线修正。

---

## 3. Phase A 与英文 OCR 先行工作

### 3.1 中文 OCR

中文 `Phase A` 的工作已经单独完成：

- GPU 环境打通
- 先做样本调参
- 再全量跑 `13` 个中文视频
- 输出 `raw/cleaned json + srt`

中文 OCR 不是本文件的主角，但它的重要性在于：

- 它提供了稳定的中文 `cue` 数据
- 它给 `Phase B` 提供了可复用的清洗规则

### 3.2 英文 OCR

后来又把 `4` 个 `part` 的英文硬字幕全部跑了 OCR：

- `part01`
- `part02`
- `part03`
- `part04`

产物目录：

- [english_ocr_4parts_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/english_ocr_4parts_v1)

工程上的收获是：

- 英文 OCR 比 Whisper 更适合作为主轴
- 但英文 OCR 也并非没有噪声
- 它会带 UI、地点、全大写提示、说话人前缀混杂

所以 OCR 只是把主源层级统一，不是自动解决对齐。

---

## 4. 第一阶段 Phase B：全局语义匹配

### 4.1 直觉上的初版方案

当中英两边都有 OCR 之后，最直观的办法是：

1. 为英文文本做 embedding
2. 为中文文本做 embedding
3. 在时间或顺序约束下做匹配

这个方法逻辑上没错，所以它是合理的第一版。

### 4.2 实际做法

这一阶段的核心脚本逐步演化为：

- [phase_b_semantic_align.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/phase_b_semantic_align.py)
- [phase_b_sequence_align.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/phase_b_sequence_align.py)

主要工程动作包括：

- 多语言 embedding
- clip 到 part 的候选挂载
- 只在候选 part 内做顺序对齐
- 加时间窗/进度约束
- 加 speaker compatibility
- 清洗 UI、地点前缀、纯音效文本

### 4.3 为什么它没有彻底成功

这一阶段已经能产出局部可用结果，但没有形成完整可交付结果。

原因不是“模型完全没用”，而是结构性问题逐渐暴露：

- 英文和中文的切分粒度不同
- 有些英文段太长
- 有些中文段太碎
- 一旦英文段落内部包含多句对白，对齐就会只挂上一句中文

工程上这一步的价值是：

- 证明“局部高置信对齐”是可能的
- 暴露“单元设计有问题”

这两点都很关键。

---

## 5. 第二阶段：先收高置信锚点，不再信全量自动结果

### 5.1 为什么要转向锚点思路

当全量自动对齐看起来“部分对、部分乱”的时候，一个常见错误是：

- 继续拧阈值
- 继续换模型
- 继续跑全量

这往往只会不断产出不同形态的噪声。

更稳的做法是先问：

- 哪些结果我们已经比较相信？
- 能不能先把这些高置信结果保存下来，当作后续工作的锚点？

所以这里做了 `hybrid high-confidence subset`。

### 5.2 具体产物

- [phase_b_bilingual_hybrid_highconf_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_bilingual_hybrid_highconf_v1.json)
- [phase_b_bilingual_hybrid_highconf_v1.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_bilingual_hybrid_highconf_v1.tsv)

对应脚本：

- [build_phase_b_hybrid_highconf.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_hybrid_highconf.py)

### 5.3 策略

这一步没有一刀切选一个版本，而是“按 part 选最佳版本”：

- `part01` 取 `mpnet_v2`
- `part02` 取 `mpnet_v4`
- `part03` 暂不保留
- `part04` 取 `mpnet_v2`

工程上这是个很实用的思路：

- 不强求一个模型统治全部场景
- 局部最优可以组合

### 5.4 结果

得到总计 `22` 条高置信候选：

- `part01: 9`
- `part02: 11`
- `part03: 0`
- `part04: 2`

这意味着：

- 方法不是完全失败
- 但产物更像“可靠锚点”，不是完整双语时间轴

这是第二个关键认识。

---

## 6. 第三阶段：锚点局部扩展

### 6.1 为什么从锚点扩出去

有了 `22` 条锚点后，很自然的下一步是：

- 不再全局乱搜
- 只围绕锚点局部扩展

这样能利用已经验证过的结果，降低错误扩散范围。

### 6.2 具体产物

- [phase_b_anchor_expansion_v2.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_anchor_expansion_v2.json)
- [phase_b_anchor_expansion_v2.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_anchor_expansion_v2.tsv)

对应脚本：

- [build_phase_b_anchor_expansion.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_anchor_expansion.py)

### 6.3 结果

局部扩展后的统计：

- `part01: 22`
- `part02: 25`
- `part04: 5`

相比 `22` 条锚点，这已经明显扩开了。

### 6.4 暴露出来的新问题

这一步虽然扩大了覆盖率，但也开始暴露更深层的问题：

- 英文 block 内多句对白只挂上一句中文
- 上一句中文串到下一句
- 同一句中文被不同 block 重复利用
- 输出上看起来像“局部能对，连续性差”

这一步的重要性在于：

- 它不是最终方案
- 但它把“问题根因”逼出来了

也就是：**alignment unit 不对**

---

## 7. 第四阶段：问题诊断从“调模型”转为“改单元”

### 7.1 触发诊断升级的信号

用户人工审查后指出了很多具体问题 ID，例如：

- `blk_0193`
- `blk_0194`
- `blk_0195`
- `blk_0196`
- `blk_0236`
- `blk_0240`
- `blk_0493`
- `blk_0514`
- `blk_0544`

这些问题有不同表象，但工程上它们指向的是一类共同症状：

- 漏译
- 串位
- 多句英文只挂一条中文

这时如果还继续“换 embedding / 调阈值”，其实是在错误层面上继续优化。

### 7.2 真正的结构问题

最终定位到的核心问题是：

**英文侧过早合并成了 block。**

这会导致：

- 英文一个 block 里有 2 到 3 句对白
- 中文却还是一条条 cue
- 对齐算法只能给 block 挂一个最相近的中文
- block 里剩余句子系统性丢失

这就是为什么会出现：

- `Now, stand back... / For what? / You'll see.`
  最后只挂上第一句中文

### 7.3 这一步的工程教训

非常重要的一条工程经验：

> 当错误模式在多个样本上重复出现，而且都指向相同的结构缺陷时，不要再继续调参数，要回到数据单元设计。

这条经验在很多工程任务里都成立，不只是字幕对齐。

---

## 8. 第五阶段：正式切换到 cue-level 路线

### 8.1 新路线的核心思想

路线冻结为：

- 英文不再用 merged block 当对齐单元
- 回到英文原始 `cue`
- 中文保持原始 `cue`
- 只在现有锚点 cluster 的局部窗口里对齐
- 支持 `1:1 / 1:N / N:1`

注意这里不是“全盘推翻之前工作”，而是：

- 保留现有锚点窗口
- 只替换窗口内的对齐单元和对齐方式

这是非常典型的工程优化方式：

- 尽量保留已验证有效的部分
- 只重构已经确定是瓶颈的那一层

### 8.2 新脚本

核心脚本：

- [build_phase_b_cue_local_align.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_cue_local_align.py)

关键函数：

- `load_english_raw_cues`
- `align_window`
- `refine_chinese_subset_for_row`
- `add_anchor_fallbacks`
- `postprocess_cluster_rows`
- `merge_output_fragments`
- `merge_english_fragments`

### 8.3 核心算法设计

这条新路线的算法结构是：

1. 读取英文原始 cue
2. 读取中文原始 cue
3. 只选锚点 cluster 附近的英文/中文窗口
4. 在窗口内构造 `1:1 / 1:2 / 2:1 / 2:2 / 3:1 / 1:3 ...` 候选组
5. 用 embedding + 时间进度 + 说话人一致性打分
6. 用 DP 选择最佳路径
7. 对结果做输出清洗
8. 对缺失位置用旧高置信 anchor fallback 补回

### 8.4 工程上的价值

这一步的价值不只是“效果更好”，而是：

- 模块边界更清楚
- 输入单元更合理
- 更容易局部调试
- 更方便人工检验

---

## 9. cue-level 版本的演进

### 9.1 v1：先把主路径跑通

最初的 `cue_local_align` 先只做一件事：

- 证明 cue-level 路线能跑通

它的重点不是输出漂不漂亮，而是验证：

- 原来 block 里丢掉的后半句，能不能在 cue-level 里出来

结果证明是能的。

例如：

- `cue_00346,cue_00347`
- `cue_00348`
- `cue_00353`
- `cue_00354`

这些都能开始独立挂中文。

### 9.2 v2：加 anchor fallback

问题：

- cue-level 并不是每个窗口都覆盖得完整
- 有些旧 anchor 明确是对的，但新路径没覆盖到

解决办法：

- 把旧高置信 anchor 当作 fallback 回填

这一步的工程意义是：

- 不盲信新算法
- 新旧路径并存
- 优先保留已验证正确的结果

### 9.3 v3：输出清洗

观察到的问题：

- 中文有 OCR 脏前缀
- 有残缺说话人标记
- 有地点/UI 残留

于是加了：

- 说话人 OCR 映射表
- 地点前缀清理
- 尾部残缺前缀裁剪
- 多中文子集压缩

### 9.4 v4 / v5：修正过度压缩和英文重复拼接

后续又做了两类细调：

1. 防止多说话人英文组被过度压缩成单中文
2. 去掉英文拼接时的重复句子

这体现出一个常见工程模式：

- 新策略解决主问题后，会引入新的次级副作用
- 这时不要回退主路线
- 而是做针对性的输出修整

---

## 10. 当前产物状态

截至本轮，最新产物是：

- [phase_b_cue_local_align_v5.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_cue_local_align_v5.json)
- [phase_b_cue_local_align_v5.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_cue_local_align_v5.tsv)

统计：

- `part01: 33`
- `part02: 46`

相比之前：

- 比 `22` 条高置信锚点多
- 比 `anchor_expansion_v2` 更细粒度
- 比 block 版更能把后半句挂出来

### 10.1 已确认改善的例子

#### part01 前段

原来 block 版的问题：

- `Now, stand back—and be ready. / For what? / You'll see.`
  只挂上了第一句

现在：

- `cue_00346,cue_00347 -> 2:2`
- `cue_00348 -> 1:1`

也就是：

- `半兵卫：好了，退后，准备好。 笃：准备什么?`
- `半兵卫：马上就知道了。`

#### part01 中段

原来：

- `By throwing more coals at me?`
- `By cutting through this.`

会被上一句污染

现在：

- `cue_00353 -> 1:1`
- `cue_00354 -> 1:1`

#### part01 末段

原来：

- `cue_00459`
  中文是 `笠·那就热烈欢迎一下吧`

现在：

- 已规范成 `笃：那就热烈欢迎一下吧`

#### part02 中后段

原来：

- `cue_01201`
  中文尾部残留 `笃：`

现在：

- 已清成 `（吃力）你吃太多鲑鱼了。`

#### part02 地点前缀

原来：

- `cue_01025`
  中文带 `妖怪巢穴`

现在：

- 已清成 `十兵卫：神社在山顶。`

### 10.2 仍未完全解决的问题

当前还没彻底解决的主要是两类：

1. 一些 `anchor-fallback 3:1`
   仍然是英文三句挂一条中文
2. 一些中文 OCR 本体就有脏字
   例如：
   - `好里。 半兵卫：你左臂很弱`

这说明下一轮工作重点不再是大改架构，而是：

- 定点返修
- 少量人工审查
- 输出后处理

---

## 11. 工程方法论总结

这一部分是最适合学习工程能力的部分。

### 11.1 不要把“模型问题”和“数据结构问题”混在一起

这次最容易犯的错是：

- 看到效果不好，就默认是 embedding 不够强

但实际更大的问题是：

- 英文 block 粒度错了

经验：

> 当错误呈现为稳定的结构模式时，优先检查输入单元设计，而不是先怀疑模型。

### 11.2 先收高置信锚点，再扩展

这一步非常重要。

如果一开始就追求全量自动完成，工程会失去抓手。

锚点的价值在于：

- 提供稳定参考点
- 便于人工验证
- 便于局部扩展
- 便于算法迭代时做回归对比

### 11.3 改路线时，不要推翻所有旧成果

从 block 路线切到 cue-level 路线时，没有把旧结果全部扔掉，而是：

- 保留锚点
- 保留 cluster 窗口
- 只替换局部对齐核心

这是一种非常实用的工程迭代方式。

### 11.4 输出清洗要作为正式工程步骤，而不是最后随手修

这次我们明确把这些都当成正式逻辑处理：

- 说话人 OCR 修正
- 地点前缀清理
- 尾部残缺标记清理
- 重复句压缩

这说明一个工程经验：

> 后处理不是“脏活”，而是算法系统的一部分。

### 11.5 新版本一定要保留并行产物，不要覆盖旧版

这次演进过程中一直保留了：

- `hybrid_highconf_v1`
- `anchor_expansion_v2`
- `cue_local_align_v1/v2/v3/v4/v5`

这样做的好处是：

- 随时能回看退化
- 可以比较哪个版本在哪一段更好
- 不会因为一轮实验失误把旧成果覆盖掉

这是非常重要的工程习惯。

---

## 12. 这次过程里最值得记住的具体教训

### 教训 1

**不要太早做“展示层合并”。**

英文 OCR 的 cue 被太早合成 block，直接破坏了对齐单元。

正确做法应该是：

- 对齐层保持细粒度
- 展示层再合并

### 教训 2

**先问“当前结果适合当锚点吗”，再问“它能不能全量用”。**

很多半成品结果，并不适合直接交付，但很适合作为锚点。

### 教训 3

**人工审查不是最后兜底，而是中途帮助定位根因。**

这次如果没有人工指出：

- `blk_0195`
- `blk_0196`
- `blk_0240`
- `blk_0544`

这些典型错误，工程很容易继续在错误方向上调参。

### 教训 4

**工程上“继续优化”必须具体到改哪一层。**

这次真正有效的继续优化，不是模糊地说：

- 再提精度
- 再换模型

而是非常具体地落到：

- 改 alignment unit
- 改局部对齐策略
- 改输出清洗

---

## 13. 当前推荐的下一步

在当前 `v5` 之后，最合理的下一步已经不是大改架构，而是：

1. 对 `part01/part02` 做重点问题段返修
2. 生成“重点返修清单”
3. 逐段校正少数明显不理想的条目
4. 再决定是否把同样方法扩到 `part03`

也就是说，工程重点已经从：

- 设计大方向

转移到了：

- 局部结果收口
- 验收
- 可交付性

---

## 14. 给工程学习者的最后建议

如果把这次过程浓缩成一句话，就是：

> 先让系统在局部可信，再让系统在范围上扩张；一旦发现错误模式是结构性的，就回到数据单元设计，不要死拧模型参数。

这句话适用于很多工程场景，不只是字幕对齐。

比如：

- OCR 后结构化抽取
- ASR 后说话人切分
- 视频事件对齐
- 多模态时间序列融合

本次 `Phase B` 的真正价值，不只是做出一个字幕对齐结果，而是把一条完整的工程迭代链条走清楚了：

- 从直觉方案出发
- 用实验暴露问题
- 用锚点稳住局部正确性
- 再重构核心单元
- 最后用后处理收口

这就是比较完整、比较成熟的工程推进方式。

---

## 15. 2026-04-19 的收口状态更新

在 `v8` 之后，工程继续推进到了 `v10`，这一阶段最重要的不是再换模型，而是把“剩余问题”从工程层面说清楚、固化清楚。

当前最新主产物：

- [phase_b_cue_local_align_v10.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_cue_local_align_v10.json)
- [phase_b_cue_local_align_v10.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_cue_local_align_v10.tsv)

新增的工程工具：

- [build_phase_b_cue_review.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_cue_review.py)

这个脚本的作用不是做对齐，而是把“审查口径”工程化。也就是说：

- 什么算严格版待审
- 什么算真正还值得继续返修

不再依赖临时命令，而是可以重复生成。

当前 `v10` 的结果是：

- `part01`: `33` 条局部双语段
- `part02`: `46` 条局部双语段
- `mean_match_score` 维持在上一轮同级水平

更关键的是审查状态：

- [phase_b_cue_local_align_v10_strict_review.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_cue_local_align_v10_strict_review.tsv)
- [phase_b_cue_local_align_v10_actionable_review.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_cue_local_align_v10_actionable_review.tsv)

其中：

- `strict_review` 仍然保留 `12` 条
- `actionable_review` 已经压到 `0` 条

这两个数字的含义必须区分开：

### `strict_review = 12` 不等于还有 12 条必须返工

严格版里保留的是：

- `manual-override`
- `manual-replacement`
- `anchor-fallback`
- 结构压缩条目

它更像“需要保留关注痕迹的条目”，而不是“还没做完的条目”。

### `actionable_review = 0` 才代表当前阶段性收口

可执行版已经为空，说明当前这条路线下：

- 能通过确定性规则补好的，已经补了
- 能通过局部 `cue-level` 改善的，已经改善了
- 剩下的不是“忘了修”，而是“数据源本身就只提供了这个粒度，或者只能作为人工接受项保留”

最典型的两个例子是：

1. `cue_01081~01083`

   这一组英文是 `3:1`，当前中文官方字幕在对应位置只有：

   - `笃：他除了跳下悬崖无处可逃。`

   所以这条现在被明确标成 `manual-replacement`。这不是算法没继续努力，而是中文源本身就没有把后两句独立表现出来。

2. `cue_01138~01141`

   这一组之前还是结构压缩残留，后来根据周围 OCR cue 补成：

   - `疯五郎：但袭击神官便是如此下场。`
   - `十兵卫：你算什么神官！`
   - `笃：你算什么神官！`
   - `疯五郎：迦具土来也！`

   也就是从“少一句”推进到“局部完整可读”。

### 这一阶段最值得学习的工程点

很多工程项目在收尾时会犯一个错：

- 明明已经没有“高性价比的继续自动优化空间”
- 却还不断继续拧模型或阈值

这次比较好的做法是：

1. 先把剩余问题缩成极小集合
2. 再区分：
   - 还能修的
   - 应该接受的
3. 最后把“接受的理由”写进系统

这比单纯追求“strict 清单归零”更成熟。

---

## 16. `part03` 的第二阶段推进

在 `part01/part02` 收口之后，工程没有直接宣布“全量完成”，而是把 `part03` 单独拆出来处理。

这是一个很重要的工程动作，因为它体现了：

- 不把不同成熟度的问题混在一起
- 不用已经收口的部分去掩盖没收口的部分

### 16.1 先诊断，不先硬跑

`part03` 的第一步不是继续跑更多 embedding 对齐，而是先诊断：

- 当前 `clip -> part` 映射是否稳定

对应产物：

- [phase_b_part03_probe_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_probe_v1.json)
- [phase_b_clip_remap_experiment_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_clip_remap_experiment_v1.json)

这一步最重要的收获不是“直接产出字幕”，而是把问题归因拉回了正确层级：

- `part03` 的主要问题在上游挂载
- 而不是下游 cue-level 算法本身

### 16.2 先找到有效中段

后续试验表明，`part03` 不是整体都做不出来，而是：

- 中间那一段 `37340906577-1-192`
- 明显可以起出一批高置信局部段

初版 trial：

- [phase_b_part03_trial_align_v1_highconf_080.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v1_highconf_080.json)

当时高置信结果是：

- `22` 条

这一步的工程价值在于：

- 先证明“这条路对 `part03` 不是完全无效”
- 再决定要不要继续深入

### 16.3 再做组合扫描

接着没有直接拍板，而是继续做组合扫描：

- [phase_b_part03_combo_sweep_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_combo_sweep_v1.json)

这一步的工程意义是：

- 把“我觉得哪个组合更好”
- 变成“哪组组合在 `highconf_080 / highconf_085` 上更好”

也就是把主观猜测转换为可比较指标。

### 16.4 最后做定向扫描

组合扫描之后，又进一步把问题拆成：

- 前段摆位
- 尾段增益

对应产物：

- [phase_b_part03_directed_sweep_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_directed_sweep_v1.json)

这一步给出的工程结论非常强：

- 尾段当前不是主要矛盾
- 前段才是主增益来源

更具体地说：

- `37342021653-1-192` 作为前段
- 比原来的 `37340055339-1-192` 更优

### 16.5 `part03 remap v2` 的阶段性结果

基于上面的定向扫描，最终落出：

- [phase_b_part03_trial_align_v2_frontbest_highconf_080.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v2_frontbest_highconf_080.json)

以及交付包：

- [phase_b_part03_trial_delivery_v2_frontbest](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_delivery_v2_frontbest)

当前结果：

- 高置信候选从 `22` 条提升到 `29` 条
- 审查结果：
  - `strict = 0`
  - `actionable = 0`

### 16.6 从高置信点扩成连续段

在 `29` 条高置信之后，又继续做了一层保守种子扩展：

- [phase_b_part03_seed_expansion_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_seed_expansion_v1.json)

这一层不是重新乱搜，而是：

- 用 `29` 条高置信结果当种子
- 只在同一中段邻域内往外补句

结果是：

- `29 -> 37`

并且当前审查口径下仍然保持：

- `strict = 0`
- `actionable = 0`

对应交付包：

- [phase_b_part03_seed_expansion_delivery_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_seed_expansion_delivery_v1)

### 16.7 这一阶段最值得学的工程点

如果把 `part03` 这一小段工程浓缩成一句教学建议，就是：

> 当一个子问题长期做不出来时，先把它拆成“输入是否稳定”和“算法是否有效”两个问题，不要默认是模型不够强。

这比继续盲调参数高级得多，也节省得多。

---

## 17. 总交付索引

在 `part01/part02` 的正式阶段包和 `part03` 的局部连续包都成形之后，又继续做了一个总交付索引：

- [phase_b_master_delivery_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_master_delivery_v1)

这个总索引的价值不在算法，而在工程组织：

- 不再让成果散落在多个目录里
- 不再让“accepted”和“partial”混成一句话
- 给后续人工审校、横向查看、二次加工一个统一入口

当前总索引统计：

- 总段数：`116`
- `part01`: `33`
- `part02`: `46`
- `part03`: `37`

质量分层：

- `phase-b-accepted`: `79`
- `phase-b-partial`: `37`

这一步的工程意义是：

- 让当前成果具备“可浏览、可解释、可继续扩展”的结构
- 而不是只停留在“脚本跑出了一堆 JSON/TSV”

---

## 18. `part04`：从“几乎不起作用”到“可收成 partial 包”

`part04` 的推进路径和 `part03` 不一样，它最值得记录的工程点不是“怎么继续调局部 DP”，而是：

> 先判断失败是不是来自时间坐标系错误，而不是默认语义模型没能力。

### 18.1 顺序摊窗为什么失败

一开始先沿用了比较粗的顺序摊窗思路，对 `part04` 跑了一版试探：

- [phase_b_part04_trial_align_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_trial_align_v1.json)

结果只有 `8` 条候选，而且大多数语义上明显不对。

这说明：

- `part04` 不能简单复用“按 clip 时长顺序平摊到 part 时间轴”的做法
- 问题很可能不是 OCR 本身，而是英文 OCR 所在的 **cut-time** 和语义候选所在的 **original-time** 没对齐

### 18.2 关键修正：把原始时间窗口映射回剪后时间轴

为了解决这个问题，新增了一个时间映射工具：

- [filter_time_mapper.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/filter_time_mapper.py)

以及基于它的试探脚本：

- [build_phase_b_filter_mapped_trial_align.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_filter_mapped_trial_align.py)

这里真正做的事是：

1. 从 `part04.dialogue-cut.vad-g3.filter.txt` 解析所有 `between(t, start, end)` 区间
2. 构建一套 `original-time -> cut-time` 的映射
3. 把 `semantic_candidates` 里原始时间轴上的窗口投影到 cut-time
4. 再只在这些 cut-time 局部窗口里做 cue-level 对齐

这一步很重要，因为它把问题拆成了：

- “语义候选有没有定位到正确原始片段”
- “英文 OCR 所在 cut-time 上有没有对应局部字幕段”

而不是继续把两层时间轴混在一起。

### 18.3 `part04` 的结果为什么可以接受为 partial

基于 filter-mapped 之后的试探结果：

- [phase_b_part04_filter_mapped_trial_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_filter_mapped_trial_v1.json)

总候选从原来的低质 `8` 条，提升到了 `17` 条可读结果，其中已经出现一批语义上明显正确的句子，例如：

- `Atsu: How did you even know we were here? -> 笃：你怎么知道我们在这？`
- `Kiku: Did the Spider kill Lord Tamura and his family? -> 菊：田村大人一家被蜘蛛杀了吗？`
- `Oyuki: I'm afraid so. -> 阿雪：恐怕是的。`
- `Kiku: There's something I want to show you. -> 菊：有样东西要给你看。`

这说明 `part04` 的主问题确实更像：

- 时间坐标系没对准

而不是：

- 英文 OCR 不可用
- 局部 cue-level 路线本身失效

### 18.4 为什么最后只纳入 `15` 条而不是 `17` 条

继续审查之后，发现 `17` 条里有 `2` 条属于结构压缩项：

- `2:1`
- `3:2`

这两条不是一定错误，但当前证据不足以把它们直接当“可交付稳定结果”。

所以工程上采取了更保守的做法：

1. 保留完整试验版 `17` 条，方便后续回溯
2. 抽出非结构压缩的稳定子集 `15` 条，单独导成 partial 交付包

对应子集文件：

- [phase_b_part04_partial_subset_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_partial_subset_v1.json)

对应交付包：

- [phase_b_part04_partial_delivery_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_partial_delivery_v1)

### 18.5 对总交付结构的影响

在 `part04` partial 包生成之后，又把总索引升级成：

- [phase_b_master_delivery_v2](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_master_delivery_v2)

新的总索引统计是：

- 总段数：`131`
- `part01`: `33`
- `part02`: `46`
- `part03`: `37`
- `part04`: `15`

质量分层：

- `phase-b-accepted`: `79`
- `phase-b-partial`: `52`

### 18.6 这一步最值得学的工程点

如果把 `part04` 的经验总结成一句工程建议，就是：

> 当一个分段表现明显比别的 part 差时，不要急着判定“模型不行”，先检查你是不是把不同时间坐标系混着用了。

这一步不是调参，而是修正问题表述方式。

### 18.7 `part04` 的二次收口

在 `v1` partial 之后，又继续做了两层更保守的收口：

1. 把明显合理的 `2:1` 压缩句
   - `cue_00483,cue_00484 -> 菊：这儿视野好。`
   作为人工接受压缩项纳入交付
2. 把一条已经对上但文本仍有 OCR 脏字的 `3:3` 行做确定性文本修正，而不是继续重跑算法

为此新增了：

- [build_phase_b_filtered_subset.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_filtered_subset.py)
- [build_phase_b_apply_row_overrides.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_apply_row_overrides.py)
- [phase_b_part04_row_overrides_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_row_overrides_v1.json)

最终 `part04` 的当前最佳 partial 包先收成：

- [phase_b_part04_partial_delivery_v3](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_partial_delivery_v3)

这一版统计为：

- `part04 = 16`

也就是说，`part04` 不是只靠一次 filter-mapped 试探就停下来了，而是又继续做了：

- 一层人工接受压缩
- 一层确定性文本净化

最后再并入新的总索引。

当前最新总索引：

- [phase_b_master_delivery_v4](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_master_delivery_v4)

当前总统计：

- 总段数：`132`
- `part01`: `33`
- `part02`: `46`
- `part03`: `37`
- `part04`: `16`

质量分层：

- `phase-b-accepted`: `79`
- `phase-b-partial`: `53`

### 18.8 修正 filter 双计数后的 `part04 v4`

在继续推进时，又发现 `filter_time_mapper.py` 早期版本把 `filter.txt` 里的：

- `[0:v:0]select=...`
- `[0:a:0]aselect=...`

两套 `between(t, ...)` 都一起解析了，导致：

- cut-time 区间被重复展开了一遍
- 映射总时长从真实的 `6714.75s` 被错误放大到了 `13429.5s`

虽然这没有直接毁掉 `part04` 的已有结果，但它确实是基础时间映射层的脏点。

所以后续又做了两件事：

1. 修正 [filter_time_mapper.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/filter_time_mapper.py)，只解析视频 `select`
2. 基于修正后的 source，重建 `part04` 的 partial 链条

新的当前版本先变成：

- [phase_b_part04_partial_delivery_v4](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_partial_delivery_v4)

这一版的工程意义不在于段数继续增加，而在于：

- 结果现在建立在正确的 cut-time 映射基础上
- `part04` 的交付链条和基础时间坐标系已经自洽

在这个基础上，又把总索引推进到：

- [phase_b_master_delivery_v6](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_master_delivery_v6)

### 18.9 `part04` 的跨 part 扩展

在修完 filter 双计数之后，没有直接停下，而是进一步做了一个关键判断：

> `part04` 的大空白区，到底是真的没有候选，还是候选其实藏在“当前分配给别的 part 的 clip”里？

为此新增了：

- [build_phase_b_part04_candidate_scan.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_part04_candidate_scan.py)
- [phase_b_part04_candidate_scan_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_candidate_scan_v1.json)

扫描结果表明：

- 至少有 `5` 个当前挂在其他 part 的中文 clip，在 `part04` 上存在还不错的语义候选窗口

随后又对这些跨 part 候选做了定向试验：

- [phase_b_part04_crosspart_trial_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_crosspart_trial_v1.json)

其中最有效的是：

- `37342350276-1-192`

它在 `part04` 的 `915s -> 968s` 附近，形成了一小段质量不错的局部连续对白。

基于这批新增结果，又继续做了：

1. 稳定子集抽取
2. 与现有 `part04` partial 子集合并

新增工具：

- [build_phase_b_merge_subsets.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_merge_subsets.py)

最终把 `part04` 推进到：

- [phase_b_part04_partial_delivery_v5](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part04_partial_delivery_v5)

这一版统计变成：

- `part04 = 25`

也就是说，`part04` 不再只是“头尾两小块 partial”，而是已经通过跨 part 候选补进了一段更早的局部连续块。

### 18.10 `part04` 的 frontier 收口

在继续补洞之后，又额外做了两轮定向试验：

- `part04_tail_candidates_trial_v1`
- `part04_midgap_trial_v1`

结果都没有产出新的可用行。

这一步很重要，因为它把“还没做”与“做过但当前自动路线没有收益”明确区分开了。

为了避免后面重复踩这些已经验证低收益的路线，又把当前前沿判断固化成：

- [phase_b_frontier_report_v1.md](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_frontier_report_v1.md)

这份 frontier 报告的核心结论是：

- `part04` 当前最大的自动收益已经基本释放完
- 真正有效的提升来自：
  - filter-mapped 实时间轴修正
  - 一段跨 part 候选扩展
- 而中段和尾段的进一步定向试验，当前已经没有给出新的可用行

这意味着后面如果还要继续补 `part04`，更可能需要：

- 更强的上游重挂载
- 或者人工锚点/人工修订

而不是再继续小幅拧当前这套自动局部对齐参数。

---

## 19. 从自动探索转向人工精选修订包

在 `part04` 的 frontier 跑清楚之后，这一阶段又补了一个新的工程出口：

- [build_phase_b_curation_pack.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_curation_pack.py)
- [phase_b_curation_pack_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_curation_pack_v1)

这一步的目标不是再自动生成更多段，而是把当前最值得人工投入的内容集中出来。

为什么这一步重要：

1. `master_delivery_v9` 已经有 `141` 条  
   直接人工看全量，成本高而且注意力会被低价值条目稀释。

2. 真正值得人工看的，不是“所有结果”  
   而是：
   - `phase-b-partial`
   - 带 `manual-override / manual-replacement / anchor-fallback`
   - 以及 accepted 里分数偏低但仍被保留的边界项

3. 这一步把“工程继续推进”从：
   - 再去盲调自动链路
   
   转成：
   - 对高价值小集合做人工精修

当前 curation pack 统计：

- 总条数：`100`
- 高优先级：`22`
- 中优先级：`78`

最重要的入口不是全表，而是：

- [shortlist_high_priority.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_curation_pack_v1/shortlist_high_priority.tsv)

如果把这一步浓缩成一句工程建议，就是：

> 当自动路线的边际收益下降时，最好的继续方式不是停下来，而是把“人工时间”也工程化。

---

## 20. 从自动产物到人工精修闭环

前面的工作已经把 `Phase B` 推到了一个很明确的边界：

- 自动局部对齐还能产生价值
- 但继续盲扩，边际收益越来越低
- 当前真正剩下的问题，越来越像人工判断题，而不是继续调一轮模型参数

因此后续工程重点不再是“继续造更多 partial 包”，而是把人工精修也做成一条稳定链路。

### 20.1 目标变化

这一阶段的目标不是再提高 `master_delivery_v9` 的段数，而是补齐这 4 个环节：

1. `review patch template`
2. `reviewed master`
3. `final export`
4. `round-based human review`

也就是说，工程焦点从：

- 自动生成更多候选

转成：

- 让人工修订结果能回写、可追踪、可重新导出

### 20.2 新增脚本

为了补齐这条链路，新增了 3 个核心脚本：

- [build_phase_b_review_patch_template.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_review_patch_template.py)
- [merge_phase_b_review_results.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/merge_phase_b_review_results.py)
- [export_reviewed_bilingual_json.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/export_reviewed_bilingual_json.py)

它们分别负责：

1. 从 review round 生成可填写的 patch 模板
2. 把人工 review 结果写回 reviewed master
3. 从 reviewed master 导出最终双语 JSON

### 20.3 已经生成的基线产物

这一步不是只写了脚本，还实际落了第一轮产物。

#### round patch 模板

已经生成：

- [phase_b_review_patch_round_a_compression_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_round_a_compression_v1)
- [phase_b_review_patch_round_b_wording_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_round_b_wording_v1)
- [phase_b_review_patch_round_c_anchor_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_round_c_anchor_v1)
- [phase_b_review_patch_round_d_partial_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_round_d_partial_v1)

每个目录里都有：

- `template.json`
- `template.tsv`
- `README.md`

其中 `template.json` 是后续 merge 的真实输入，`template.tsv` 只是便于快速浏览。

#### reviewed master 基线

在还没有人工 patch 的情况下，已经先生成了 reviewed master 基线：

- [phase_b_master_reviewed_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_master_reviewed_v1)

它把当前 `master_delivery_v9` 的 `141` 条统一标成了 review 状态：

- `auto-accepted: 41`
- `needs-review: 100`

这一步的重要性在于：

- 它第一次把“自动结果”和“待审结果”正式区分开了
- 后面人工 patch 不再直接改 master，而是改 reviewed master 的状态

#### final export 基线

基于 reviewed master，又导出了一版仅包含可直接放行状态的 final baseline：

- [phase_b_final_export_v1_auto_baseline](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_final_export_v1_auto_baseline)

当前导出的状态集合是：

- `auto-accepted`
- `confirmed`
- `revised`
- `split-derived`

因为目前还没有人工 patch，所以这版 baseline 实际只导出了：

- `41` 条 `auto-accepted`
- 覆盖 `part01 / part02`

这不是最终成品，但它证明了：

- `reviewed master -> final bilingual json`

这条链路已经能正常跑通。

### 20.4 review_status 机制为什么关键

在没有 `review_status` 之前，工程上只有两种粗粒度标签：

- `phase-b-accepted`
- `phase-b-partial`

这不足以支持人工收口，因为它不能回答这些问题：

- 哪条还没审
- 哪条已经人工确认
- 哪条已人工改写
- 哪条应该排除
- 哪条是 split 后生成的新条目

所以 reviewed master 引入了更细的状态：

- `auto-accepted`
- `needs-review`
- `confirmed`
- `revised`
- `excluded`
- `superseded-by-split`
- `split-derived`

这一层状态不是“多余标签”，而是把后续人工工作从散乱文本修改，变成了可追踪的工程流。

### 20.5 这一步的工程意义

如果把这一阶段压缩成一句话，它解决的是：

> 以前我们只有“候选结果”，现在我们开始具备“可闭环的生产链路”。

这意味着后面的工作重心已经变了：

- 不是继续问“还能不能自动补 5 条”
- 而是开始问“哪些条目值得人工花时间，以及修完后怎么稳定回写”

这也是工程推进中一个非常典型的拐点：

- 早期拼探索能力
- 中期拼问题诊断
- 后期拼收口机制

`Phase B` 现在已经进入第三种状态。

---

## 21. 第一轮高优先级人工 review 完成

在继续自动探索已经明显收益递减之后，后续工作正式切到了人工精修闭环。

这一轮并不是只做了 review 文件，而是把整条链路真正跑通了：

1. 生成 review patch 模板
2. 人工填写 `round_a / round_b / round_c / round_d`
3. merge 回 reviewed master
4. 从 reviewed master 导出 final bilingual json

### 21.1 新增脚本

这一步新增了 3 个关键脚本：

- [build_phase_b_review_patch_template.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_review_patch_template.py)
- [merge_phase_b_review_results.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/merge_phase_b_review_results.py)
- [export_reviewed_bilingual_json.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/export_reviewed_bilingual_json.py)

### 21.2 reviewed master 演化

这条链路的 reviewed master 版本演化是：

- `v1`: 无 patch，仅建立 review 状态基线
- `v2`: 合并 `round_a`
- `v3`: 合并 `round_a + round_b`
- `v4`: 合并 `round_a + round_b + round_c`
- `v5`: 合并 `round_a + round_b + round_c + round_d`

当前正式主基线是：

- [phase_b_master_reviewed_v5](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_master_reviewed_v5)

其统计为：

- `auto-accepted`: `41`
- `confirmed`: `20`
- `revised`: `2`
- `needs-review`: `78`

### 21.3 final export 演化

final export 也同步演化：

- `v1_auto_baseline`
- `v2_round_a`
- `v3_round_ab`
- `v4_round_abc`
- `v5_round_abcd`

当前最新导出：

- [phase_b_final_export_v5_round_abcd](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_final_export_v5_round_abcd)

统计为：

- 总导出：`63`
- `part01`: `21`
- `part02`: `32`
- `part04`: `10`

### 21.4 这一步的工程意义

这轮工作的真正意义，不是“多确认了 22 条”这么简单，而是：

- `Phase B` 第一次拥有了真正稳定的人工收口机制
- 后面继续审中优先级 `78` 条时，不需要再临时发明流程
- reviewed master / final export 已经变成稳定的生产链路，而不是一次性脚本结果

如果要提炼成一句工程建议，就是：

> 自动链路跑到边界之后，最重要的不是再找新模型，而是把人工判断变成可回写、可导出、可版本化的正式流程。

---

## 22. 中优先级 78 条的批次化准备

在第一轮高优先级 `22` 条 review 完成之后，下一步自然就变成：

- 如何处理剩下的 `78` 条 `needs-review`

这里如果直接把 `78` 条一股脑交给人工去看，会马上产生两个工程问题：

1. 一次 review 负担太重
2. 不同类型问题混在一起，审核心智成本太高

所以这一步没有直接继续生成一个大 patch 模板，而是先做“批次化准备”。

### 22.1 新增脚本

- [build_phase_b_medium_review_batches.py](/C:/Users/汪家俊/anime/AnimeTranscoder/tools/build_phase_b_medium_review_batches.py)

它的目标不是再筛选，而是把已经确定的 `78` 条中优先级结果拆成更合适的 review 批次。

### 22.2 为什么不平均分

这一步刻意没有按“每批大约 20 条”生硬均分，而是按真实工作面拆：

- `part01` 已接受但分数偏低的一批
- `part02` 已接受但分数偏低的一批
- `part04` 的 partial 一批
- `part03` 的 partial 再拆成前后两半

这样做的好处是：

- 同一批里的问题类型更接近
- 人工 review 时不需要频繁切换判断模式
- 后续 merge 后更容易判断哪一类结果最稳定、哪一类仍然薄弱

### 22.3 当前批次结构

批次目录：

- [phase_b_medium_review_batches_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_medium_review_batches_v1)

统计如下：

- `medium_batch_01_part01_accepted`: `12`
- `medium_batch_02_part02_accepted`: `14`
- `medium_batch_03_part04_partial`: `15`
- `medium_batch_04_part03_partial_a`: `19`
- `medium_batch_05_part03_partial_b`: `18`

总计正好 `78` 条。

### 22.4 patch 模板也已经同步生成

为了避免“只是拆批次，但后续还得再手动搭 review 模板”，这一步又直接把 5 个 patch 模板一起生成了：

- [phase_b_review_patch_medium_batch_01_part01_accepted_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_medium_batch_01_part01_accepted_v1)
- [phase_b_review_patch_medium_batch_02_part02_accepted_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_medium_batch_02_part02_accepted_v1)
- [phase_b_review_patch_medium_batch_03_part04_partial_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_medium_batch_03_part04_partial_v1)
- [phase_b_review_patch_medium_batch_04_part03_partial_a_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_medium_batch_04_part03_partial_a_v1)
- [phase_b_review_patch_medium_batch_05_part03_partial_b_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_review_patch_medium_batch_05_part03_partial_b_v1)

也就是说，到这一步为止：

- 高优先级 `22` 条：已 review 完成并已并入 `v5`
- 中优先级 `78` 条：已拆批次，已生成 patch 模板，随时可以继续填

### 22.5 当前最合理的后续顺序

如果继续往下做，我建议顺序是：

1. `medium_batch_01_part01_accepted`
2. `medium_batch_02_part02_accepted`
3. `medium_batch_03_part04_partial`
4. `medium_batch_04_part03_partial_a`
5. `medium_batch_05_part03_partial_b`

原因很简单：

- 先处理已经比较接近 accepted 的 `part01 / part02`
- 再处理 `part04 partial`
- 最后再啃 `part03`，因为它仍然是结构最不稳定的一组

---

## 23. 中优先级 78 条 review 完成，形成 v6 全量 reviewed 基线

在批次和 patch 模板准备完之后，后续这 `5` 个中优先级批次也全部进入了实际人工回写：

- `medium_batch_01_part01_accepted`
- `medium_batch_02_part02_accepted`
- `medium_batch_03_part04_partial`
- `medium_batch_04_part03_partial_a`
- `medium_batch_05_part03_partial_b`

这些 reviewed patch 全部 merge 之后，形成了新的主基线：

- [phase_b_master_reviewed_v6](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_master_reviewed_v6)

统计变成：

- `auto-accepted`: `41`
- `confirmed`: `83`
- `revised`: `17`
- `needs-review`: `0`

这一步非常关键，因为它意味着：

- 当前 `master_delivery_v9` 的全部 `141` 条结果
- 已经全部进入 review 闭环

换句话说，到这里为止，`Phase B` 不再只是“部分 reviewed”，而是第一次拥有了一版全量 reviewed 的统一主基线。

对应的全量导出也随之生成：

- [phase_b_final_export_v6_medium1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_final_export_v6_medium1)

统计为：

- 总导出：`141`
- `part01`: `33`
- `part02`: `46`
- `part03`: `37`
- `part04`: `25`

也就是说，当前基于 `master_delivery_v9` 的所有候选，已经全部出现在 reviewed final export 里。

### 23.1 为什么这一步是工程里真正的阶段终点

如果把整条路线回头看，会发现：

- 最初我们解决的是“候选怎么生成”
- 中期解决的是“结构为什么会错”
- 后期解决的是“人工判断怎么回写”

而 `v6` 这一步是三者真正汇合的地方：

- 有自动候选
- 有人工回写
- 有统一导出

这意味着后面如果还要继续做，就不再是“把当前流程补完整”，而是：

- 冻结当前版本
- 做质量复盘
- 或者重开上游优化

### 23.2 这一步最值得记住的工程结论

> 工程的完成，不只是模型跑完，也不是文件变多，而是从输入到人工判断再到导出，整条链路都能稳定闭环。

`v6` 就是这次 `Phase B` 第一次真正达到这个状态的版本。
