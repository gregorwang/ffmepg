# Ghost Yotei 双语字幕项目 新对话交接文档

## 1. 这份文档的用途

这份文档是给“新开对话”的助手看的交接说明。

目标不是回顾所有历史细节，而是让新对话在最短时间内准确理解：

- 当前项目真正目标是什么
- 哪些工作已经完成
- 哪些地方容易误解
- 当前官方版本在哪里
- 下一步应该做什么

请把这份文档当成当前项目的交接起点，而不是从零重新理解全部历史。

---

## 2. 项目真正目标

当前项目的真正目标是：

**为 Ghost Yotei 的 4 个英文 part 重建“完整全篇双语字幕轨”。**

这里的“完整全篇双语字幕轨”指的是：

- 以英文字幕为主轴
- 对应挂上中文字幕
- 最终产出机器可读的双语 JSON / SRT / ASS
- 后续可以用于烧录或进一步人工校对

请注意：

**当前项目已经完成的，不是完整全篇双语字幕轨。**

当前已经完成的是：

- 一批高质量、人工确认过的双语对齐段
- 它们非常有价值
- 但它们只是“精选对齐结果”，不是“全片完整轨”

---

## 3. 当前最重要的纠偏结论

这是整个交接里最重要的一条：

### 3.1 `141` 不是全片字幕总数

当前官方交付里有 `141` 条双语段。

这个数字 **不是**：

- 所有英文字幕总数
- 所有中文字幕总数
- 全片完整对齐后的最终句数

这个数字实际表示的是：

**当前这一轮高质量双语对齐后，被纳入主交付的双语段数。**

也就是说：

- `141` 是精选结果
- 不是完整轨

### 3.2 真正的原始规模

英文 OCR 原始 cleaned cue 总数：

- `part01 = 1249`
- `part02 = 1444`
- `part03 = 1354`
- `part04 = 1111`
- 合计 `5158`

中文 OCR cleaned cue 总数：

- 来自 `13` 个中文切片视频
- 合计 `4423`

所以当前真实问题不是“还差几十句”，而是：

**还差几千句规模的完整轨重建。**

### 3.3 当前还不能直接做“最终全片烧录”

我们已经可以做：

- 当前 `141` 段的局部双语烧录

但还不能说：

- 已经具备“完整全片双语字幕烧录”的前提

因为完整轨还没重建出来。

所以新对话不能把“当前已有 141 段双语结果”误当成最终全片字幕轨。

---

## 4. 当前已完成工作

### 4.1 中文 OCR

中文侧已经完成：

- `13` 个中文切片视频的 OCR
- 已有 cleaned JSON / SRT
- 目录在：

`C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea`

每个视频目录里都有 `cleaned.json / cleaned.srt / raw.json / raw.srt`

中文 OCR cleaned 总量：

- `4423` 条

### 4.2 英文 OCR

英文侧已经完成：

- 4 个 `part` 的 OCR
- 已有 cleaned JSON / SRT

目录在：

`C:\Users\汪家俊\anime\AnimeTranscoder\scratch\english_ocr_4parts_v1`

分 part 的 cleaned 数量：

- `part01 = 1249`
- `part02 = 1444`
- `part03 = 1354`
- `part04 = 1111`

### 4.3 Phase B 高质量双语对齐与人工 review

我们已经做完一条完整的高质量对齐流水线：

- 自动对齐
- 多轮人工 review
- 多轮修订
- 最终收口

最终得到：

- `141 / 141` 全部人工确认完成的双语段

当前最终高质量交付版本是：

#### 官方 reviewed master

`C:\Users\汪家俊\anime\AnimeTranscoder\scratch\phase_b_master_reviewed_v14_round8`

#### 官方 final export

`C:\Users\汪家俊\anime\AnimeTranscoder\scratch\phase_b_final_export_v14_round8`

#### 官方冻结快照

`C:\Users\汪家俊\anime\AnimeTranscoder\scratch\phase_b_release_v14_round8_frozen`

#### 当前官方版本标记

`C:\Users\汪家俊\anime\AnimeTranscoder\scratch\PHASE_B_CURRENT_OFFICIAL_VERSION.txt`

### 4.4 这 `141` 条已经全部 confirmed

当前 `v14_round8` 的状态：

- `confirmed = 141`
- `revised = 0`
- `auto-accepted = 0`

也就是说，这 `141` 条已经被全部人工确认。

它们是高质量成果，不应该被丢弃或重做。

---

## 5. 当前最容易踩的坑

新对话最容易犯的错误有 4 个：

### 5.1 误把 `141` 当成完整字幕轨

这是最危险的误解。

请再次记住：

- `141` 是精选双语对齐段
- 不是完整轨

### 5.2 继续围绕 `141` 做局部精修

这条路已经基本走到头了。

当前 `141` 条已经：

- 全部人工确认
- 不需要继续做“再精修一轮”

如果新对话继续围绕这 `141` 条做更多 review、round9、round10，那就是走偏了。

### 5.3 直接进入全片字幕烧录

当前只适合做：

- `141` 段的局部预览烧录

不适合直接声称：

- 已经具备完整全片双语烧录条件

### 5.4 忽略“完整轨重建”和“高质量精选段”是两种不同任务

之前的 Phase B pipeline 优化目标是：

- 宁可少
- 但要稳
- 只收高置信

这对“高质量精选对齐段”是对的。

但对“完整全篇字幕轨重建”是不对的。

完整轨必须换目标：

- 先追求覆盖率
- 再做质量分层
- 最后再人工复核边缘项

---

## 6. 当前下一阶段的真正任务

当前新阶段的目标应该明确切换为：

## Phase C：完整全篇双语字幕轨重建

这一步不是再做精选，而是：

- 以英文 OCR 全量 `5158` 条为主轴
- 把中文 OCR 全量 `4423` 条尽可能挂上去
- 输出一个完整草稿轨

### 6.1 Phase C 的目标产物

至少应产出：

1. 全量双语草稿 JSON
2. 全量双语草稿 TSV
3. 每个 `part` 的双语草稿 SRT
4. 覆盖率统计
5. 质量分层统计

### 6.2 Phase C 的状态字段建议

不要再只保留“精选成功段”。

应当为每条英文 cue 给出类似这样的状态：

- `matched-high`
- `matched-medium`
- `matched-low`
- `unmatched`
- `merged-1n`
- `merged-n1`

也就是说，新阶段的任务不是“只输出成功项”，而是“输出完整轨 + 标记质量层级”。

---

## 7. 推荐的新对话起步路线

新对话建议不要从抽象讨论开始，而是直接按下面顺序推进：

### Step 1. 锁定当前已完成成果

把下列内容视为只读基线：

- `phase_b_master_reviewed_v14_round8`
- `phase_b_final_export_v14_round8`
- `phase_b_release_v14_round8_frozen`

这些文件的作用：

- 作为高质量人工确认样本集
- 作为 Phase C 的锚点
- 不再回头重做

### Step 2. 读取全量原始输入

英文全量：

- `scratch/english_ocr_4parts_v1/part01/cleaned.json`
- `scratch/english_ocr_4parts_v1/part02/cleaned.json`
- `scratch/english_ocr_4parts_v1/part03/cleaned.json`
- `scratch/english_ocr_4parts_v1/part04/cleaned.json`

中文全量：

- `C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea\<clip>\cleaned.json`

### Step 3. 目标从“高置信筛选”切到“完整轨覆盖”

新的对齐思路应改为：

- 英文全量 cue 作为骨架
- 对每条英文 cue 输出一条记录
- 即使匹配不稳，也不要直接丢掉
- 先保留为 `matched-low` 或 `unmatched`

### Step 4. 产出第一版全量 draft

建议命名：

- `phase_c_fulltrack_rebuild_v1`

应包括：

- `all_segments.json`
- `all_segments.tsv`
- `part01/part01.draft.srt`
- `part02/part02.draft.srt`
- `part03/part03.draft.srt`
- `part04/part04.draft.srt`

### Step 5. 再决定是否进入烧录

只有在完整轨 draft 出来之后，才重新判断：

- 是否已经够覆盖率
- 是否先做草稿版烧录预览
- 是否继续人工校正

---

## 8. 可直接给新对话的核心指令

如果要把这份文档交给新对话，建议你在开场直接说明：

### 可复制给新对话的简短指令

请先阅读 `docs/phase_b/HUMAN_ONLY__GhostYotei-新对话交接文档-20260421.md`。

当前 Ghost Yotei 项目已经完成了一轮高质量双语对齐与人工 review，官方冻结版是：

- `scratch/phase_b_master_reviewed_v14_round8`
- `scratch/phase_b_final_export_v14_round8`

但请注意，当前 `141` 条只是高质量精选双语段，不是完整全篇双语字幕轨。

真实原始规模是：

- 英文 OCR cleaned 总量 `5158`
- 中文 OCR cleaned 总量 `4423`

当前新任务不是继续精修这 `141` 条，而是启动 Phase C，重建完整全篇双语字幕轨：

- 以英文全量 cue 为主骨架
- 输出完整草稿 JSON / TSV / SRT
- 保留质量分层和 unmatched 状态

请不要把当前阶段误判成“已经可以完整烧录最终全片”，先做完整轨 draft。

---

## 9. 本文档的结论

一句话总结当前状态：

**Phase B 的“高质量精选双语段”已经彻底完成，Phase C 的“完整全篇双语轨重建”还没开始。**

新对话应该从这里继续，而不是继续围绕 `141` 条做局部精修。
