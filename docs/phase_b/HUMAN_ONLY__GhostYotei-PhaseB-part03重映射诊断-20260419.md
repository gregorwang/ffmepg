# Ghost Yotei Phase B part03 重映射诊断

## 1. 这份文档回答什么问题

这份文档只回答一个问题：

> 为什么 `part03` 一直没有像 `part01/part02` 那样进入可收口状态？

结论先写在前面：

- `part03` 当前的主要问题不是 `cue-level` 对齐算法本身
- 而是更上游的 **clip -> part 挂载不稳**
- 所以当前不应该继续直接把 `part03` 塞进 `cue-level` 局部对齐流程
- 应该先重开一次 **片段重映射实验**

---

## 2. 当前证据

### 英文侧

当前英文 OCR 结果：

- [part03 cleaned.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/english_ocr_4parts_v1/part03/cleaned.json)

统计：

- cue 数量：`1354`
- 英文 OCR 时间轴范围：`0.0 -> 6132.0`
- 英文 OCR 时长：`6132.0s`

这和 `part03` 目标 cut 时长 `6128.8s` 基本一致。

也就是说：

- 英文侧时间轴本身是成立的
- `part03` 的问题不在英文 OCR 时长

### 中文侧

当前被分配给 `part03` 的中文片段是：

- `37340906577-1-192`
- `37342021653-1-192`
- `37342350276-1-192`

来自：

- [clip_part_mapping.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_semantic_v4/clip_part_mapping.json)

原始分配统计：

- `part03 target_cut_duration = 6128.8s`
- `assigned_clip_duration = 7219.028s`
- `duration_gap_seconds = +1090.228s`

这个缺口非常大。

如果 `part03` 真的是正确挂载，这个正偏差不该这么夸张。

---

## 3. 第一份诊断产物

结构化诊断文件：

- [phase_b_part03_probe_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_probe_v1.json)
- [phase_b_part03_probe_v1.md](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_probe_v1.md)

这个 probe 的核心结论是：

- `assigned_clip_count = 3`
- `stable_clip_count = 1`
- `ambiguous_or_worse_count = 2`

也就是说：

- 当前 3 个片段里，只有 1 个对 `part03` 的挂载是稳定的
- 另外 2 个已经不够稳，甚至有明确错挂迹象

### 3.1 各片段状态

#### `37340906577-1-192`

- `score_margin = +0.0999`
- 状态：`stable`

这说明这个片段属于 `part03` 的证据比较强。

#### `37342021653-1-192`

- `score_margin = -0.0307`
- 状态：`ambiguous`

这里已经不是“置信度不高”，而是：

- 最佳备选 part 的分数已经高于当前 assigned part

#### `37342350276-1-192`

- `score_margin = -0.0992`
- 状态：`misassigned-likely`

这是最关键的一条。

它当前挂在 `part03`，但：

- `ghost-yotei-part04` 的候选分数 `0.7208`
- 明显高于 `ghost-yotei-part03` 的 `0.6216`

这说明这条非常可能本来就不该挂在 `part03`。

---

## 4. 第二份诊断产物：受限重映射实验

为了不只停留在“看起来像挂错了”，又跑了一次受限重映射实验：

- [phase_b_clip_remap_experiment_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_clip_remap_experiment_v1.json)

这个实验做的事情很简单：

- 对全部 `13` 个中文片段
- 只在各自前 `2` 名语义候选里重新组合
- 同时考虑：
  - 语义总分
  - 各 `part` 的总时长偏差

它不是最终算法，只是一个工程判别工具，用来回答：

> 当前 clip-part 挂载，是否已经卡住了更好的全局组合？

---

## 5. 实验结果

### 基线（当前分配）

- `semantic_total = 8.3974`
- `duration_gap_sum = 2447.286`

其中 `part03`：

- `target = 6128.8`
- `assigned = 7219.028`
- `gap = +1090.228`

### 最优候选（在 top-2 备选里重排）

- `semantic_total = 8.6433`
- `duration_gap_sum = 1928.806`

其中 `part03`：

- `target = 6128.8`
- `assigned = 6431.986`
- `gap = +303.186`

也就是说：

- 全局语义总分更高
- 全局时长偏差更小
- `part03` 的超长问题从 `+1090s` 压到了 `+303s`

这不是小改进，而是结构性改进。

---

## 6. 这次实验给出的关键换位

最优候选和当前分配相比，主要差异是：

- `37342350276-1-192`
  - `part03 -> part04`
- `37343464803-1-192`
  - `part04 -> part03`
- `37342021653-1-192`
  - `part03 -> part01`
- `37340055339-1-192`
  - `part02 -> part03`
- `37338680721-1-192`
  - `part01 -> part02`

这里最重要的不是“五条都要立刻采用”，而是它证明了：

### 证明 1

当前 `part03` 失败，不是因为 `part03` 天生做不了。

### 证明 2

只要上一层 clip 挂载重新打开，`part03` 的工程状态就可能明显改善。

### 证明 3

当前 `part03` 没做出来，不该被解读成“cue-level 路线在 `part03` 上无效”。

它更像是：

- cue-level 路线还没获得一个足够可信的 `part03` 输入集合

---

## 7. 当前最合理的工程结论

到这里，结论已经可以写得非常明确：

### 结论 1

`part01/part02` 当前已经进入阶段性收口。

对应交付包：

- [phase_b_delivery_v10](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_delivery_v10)

### 结论 2

`part03` 不应该继续直接沿用当前分配跑 `cue-level` 局部对齐。

### 结论 3

`part03` 的下一步，不是“继续调对齐参数”，而是：

- 单独做一次 **clip-part remap**

### 结论 4

只有 remap 之后，才有资格判断：

- `part03` 的 cue-level 局部对齐是否真的可行

---

## 8. 推荐的下一步

如果下一轮继续做 `part03`，建议按这个顺序：

1. 先基于 [phase_b_clip_remap_experiment_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_clip_remap_experiment_v1.json) 选一个试验性新分配
2. 只抽其中 1 个候选 cluster 做局部 cue-level 验证
3. 如果局部结果明显改善，再决定是否正式重开 `part03`

不建议直接做的事情：

- 不建议在当前旧分配上继续硬跑 `part03`
- 不建议直接拿 `part03` 继续做全量语义乱搜
- 不建议把 `part03` 和 `part01/part02` 的当前交付状态混在一起

---

## 9. 试探性 cue-level 验证结果

在文档初稿之后，又追加做了一次真正的试探性局部对齐，不再只停留在“应该 remap”的推断层。

新增产物：

- [phase_b_part03_trial_align_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v1.json)
- [phase_b_part03_trial_align_v1.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v1.tsv)
- [phase_b_part03_trial_align_v1_highconf_080.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v1_highconf_080.json)
- [phase_b_part03_trial_align_v1_highconf_080.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v1_highconf_080.tsv)

这次试验采用的是一组 remap-inspired 候选 clip：

- `37340055339-1-192`
- `37340906577-1-192`
- `37343464803-1-192`

并按连续伪窗口方式在 `part03` 英文 OCR 时间轴上做局部 `cue-level` 对齐。

### 9.1 结果不是平均展开的

试验结果非常不均匀：

- `37340055339-1-192`
  - 只起出 `2` 条
- `37340906577-1-192`
  - 起出 `80` 条
  - 平均分数 `0.7634`
- `37343464803-1-192`
  - 只起出 `1` 条

这说明：

- `part03` 现在不是“全段都不行”
- 而是“只有中间那一段已经开始显著起势”

### 9.2 高置信子集

按 `match_score >= 0.80` 抽出来的高置信候选共有：

- `22` 条

并且全部来自：

- `37340906577-1-192`

高置信时间范围大致落在：

- `2655s -> 3803s`

也就是说，当前最明确的工程事实是：

> `part03` 已经出现一段可以形成局部连续双语段的“有效中段”，只是还没有覆盖到其余两段候选 clip。

### 9.3 这对下一步意味着什么

这次试验把结论从“猜测”推进成了“证据”：

1. `part03` 不是完全做不出来
2. `clip-part remap` 的价值是真实存在的
3. 但 `part03` 现在还不适合直接承诺成完整局部交付包
4. 最合理的下一步是：
   - 以 `37340906577-1-192` 对应的有效中段为锚点
   - 继续尝试更合理的前后两段 clip 重分配

---

## 10. 组合扫描补充验证

在上述 trial 之后，又继续做了一轮更系统的组合扫描：

- [phase_b_part03_combo_sweep_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_combo_sweep_v1.json)

这轮不是再猜，而是直接拿 3 组最像样的三段组合去跑同一套 trial 对齐流程，比较：

- `highconf_080`
- `highconf_085`
- 平均匹配分数

### 10.1 扫描结论

当前结果非常清楚：

1. 组合 `["37340055339-1-192", "37340906577-1-192", "37343464803-1-192"]`
   - `highconf_080 = 22`
   - `highconf_085 = 8`

2. 组合 `["37340055339-1-192", "37340906577-1-192", "37342874714-1-192"]`
   - `highconf_080 = 22`
   - `highconf_085 = 8`

3. 组合 `["37340906577-1-192", "37342874714-1-192", "37343464803-1-192"]`
   - `highconf_080 = 2`
   - `highconf_085 = 0`

### 10.2 这说明什么

这说明当前真正稳定的不是“三段组合”，而是：

- 中间这段 `37340906577-1-192`

它无论配 `37343464803-1-192` 还是 `37342874714-1-192`，高置信结果都没有本质变化。

更准确地说：

- 前段 `37340055339-1-192` 目前只提供极少数低强度补充
- 中段 `37340906577-1-192` 才是当前真正产出高置信双语段的核心来源
- 尾段候选换来换去，对高置信结果几乎没有决定性提升

所以 `part03 remap v2` 的工程判断应该冻结为：

### 冻结判断

1. `37340906577-1-192` 先固定为 `part03` 的有效中段锚点
2. `37340055339-1-192 / 37342874714-1-192 / 37343464803-1-192` 这些前后段目前仍属于开放候选
3. 下一步不该再做“大范围三段组合乱试”，而应该：
   - 先围绕有效中段做局部扩展
   - 再单独研究前段和尾段怎么重挂载

---

## 11. 定向扫描：前段比尾段更重要

在组合扫描之后，又继续做了一轮更细的定向扫描：

- [phase_b_part03_directed_sweep_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_directed_sweep_v1.json)

这轮不再混着看，而是拆成两类问题：

1. **前段候选**
   - 谁最能把中段锚点摆到正确位置
2. **尾段候选**
   - 在前中段固定后，谁还能继续带来实际增益

### 11.1 前段结果

当前排序非常清楚：

1. `37342021653-1-192 + 37340906577-1-192`
   - `highconf_080 = 29`
   - `highconf_085 = 15`

2. `37343464803-1-192 + 37340906577-1-192`
   - `highconf_080 = 25`
   - `highconf_085 = 13`

3. `37340055339-1-192 + 37340906577-1-192`
   - `highconf_080 = 22`
   - `highconf_085 = 8`

4. `37342874714-1-192 + 37340906577-1-192`
   - `highconf_080 = 8`
   - `highconf_085 = 1`

也就是说，前段优先级已经明确改写了：

- `37342021653-1-192` 是当前最优前段
- 之前的 `37340055339-1-192` 已经不再是最优解

### 11.2 尾段结果

尾段扫描几乎没有带来本质变化。

不管尾段用：

- `37342021653-1-192`
- `37343464803-1-192`
- `37342874714-1-192`
- `37343791965-1-192`

最终都基本停留在：

- `highconf_080 = 22`
- `highconf_085 = 8`

这说明：

- **当前阶段尾段不是主要矛盾**
- 真正值得动的是前段摆位

---

## 12. `part03 remap v2` 当前最佳局部成果

基于上面的定向扫描，已经把当前最佳前段方案单独落了一版正式试验结果：

- [phase_b_part03_trial_align_v2_frontbest.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v2_frontbest.json)
- [phase_b_part03_trial_align_v2_frontbest.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v2_frontbest.tsv)

其高置信子集是：

- [phase_b_part03_trial_align_v2_frontbest_highconf_080.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v2_frontbest_highconf_080.json)

当前统计：

- `highconf_080 = 29`
- `strict = 0`
- `actionable = 0`

对应审查文件：

- [phase_b_part03_trial_align_v2_frontbest_highconf_080_strict_review.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v2_frontbest_highconf_080_strict_review.tsv)
- [phase_b_part03_trial_align_v2_frontbest_highconf_080_actionable_review.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_align_v2_frontbest_highconf_080_actionable_review.tsv)

并且已经导出为一个可直接审的局部候选包：

- [phase_b_part03_trial_delivery_v2_frontbest](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_trial_delivery_v2_frontbest)

这一步的意义在于：

- `part03` 的高置信局部候选，已经从 `22` 条提高到 `29` 条
- 提升不是通过继续乱调尾段得来的
- 而是通过更合理的 **前段 remap**

---

## 13. 保守种子扩展：`29 -> 37`

在 `v2 frontbest` 之后，又继续做了一层更保守的局部扩展：

- [phase_b_part03_seed_expansion_v1.json](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_seed_expansion_v1.json)
- [phase_b_part03_seed_expansion_v1.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_seed_expansion_v1.tsv)

这一步不是重新全局搜索，而是：

1. 以 `v2 frontbest` 的 `29` 条高置信结果为种子
2. 只在同一中段邻域内
3. 用更保守的邻近阈值把句子向外补一圈

当前结果：

- 局部连续段从 `29` 条提升到 `37` 条
- 审查结果仍然是：
  - `strict = 0`
  - `actionable = 0`

对应审查文件：

- [phase_b_part03_seed_expansion_v1_strict_review.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_seed_expansion_v1_strict_review.tsv)
- [phase_b_part03_seed_expansion_v1_actionable_review.tsv](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_seed_expansion_v1_actionable_review.tsv)

交付包：

- [phase_b_part03_seed_expansion_delivery_v1](/C:/Users/汪家俊/anime/AnimeTranscoder/scratch/phase_b_part03_seed_expansion_delivery_v1)

### 13.1 这一步意味着什么

这一步非常关键，因为它说明：

- `part03` 当前不仅能拿到一批高置信点
- 还能在不引入明显结构问题的前提下，扩成一小段更连续的局部双语块

也就是说，`part03` 的当前最佳状态已经从：

- `29` 条高置信候选

推进到了：

- `37` 条保守扩展后的局部连续段

---

## 14. 一句话总结

如果把这次 `part03` 的判断浓缩成一句话，就是：

> `part03` 现在不是“对齐失败”，而是“输入挂载还没稳定到足够让对齐开始成功”。`
