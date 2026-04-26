# Ghost Yotei Phase C `gpt-5.2-mini` 新会话操作文档

## 1. 这份文档是干什么的

这是一份给 **新开的 Codex 会话里的 `gpt-5.2-mini`** 用的操作文档。

它的目的不是回顾全部历史，而是把 **当前真正有效的主线、当前已经做到哪里、接下来 mini 要干什么、怎么干、输入在哪里、输出应该长什么样、哪些东西不要碰** 一次讲清楚。

如果你准备开一个新会话，让 `gpt-5.2-mini` 接手 Phase C 后续精修，这份文档就是它的主操作说明。

---

## 2. 先看结论

### 2.1 当前主线已经不是旧的 `no-match closure` 分支

当前有效主线是：

- `scratch\phase_c_english_first_forced_rematch_v7_parttail`

不是下面这些旧收尾目录：

- `phase_c_predecision_applied_v3_complete`
- `phase_c_portal_v1_complete`
- `phase_c_dashboard_v1_complete`
- `phase_c_release_snapshot_v1_complete`

这些旧目录描述的是之前那条“把 review 行全部关单”的分支，**不应再视为当前匹配主线**。

### 2.2 当前任务目标

当前目标非常明确：

1. 以 **英文时间轴 OCR cue** 为唯一骨架。
2. 把中文 OCR 文本尽可能挂到英文 cue 上。
3. **先追覆盖率，再追精度**。
4. 多余中文可以丢，不必强保留。
5. 时间轴先不重做，后面再根据英文时间轴校正。

### 2.3 当前真实进度

当前主线结果：

- 英文总 cue：`5158`
- 当前已匹配：`4620`
- 当前未匹配：`538`
- 当前覆盖率：`89.57%`

分 part 情况：

- `ghost-yotei-part01`: `1229 / 1249 = 98.40%`
- `ghost-yotei-part02`: `1311 / 1444 = 90.79%`
- `ghost-yotei-part03`: `1354 / 1354 = 100.00%`
- `ghost-yotei-part04`: `726 / 1111 = 65.35%`

当前最大短板是：

- `ghost-yotei-part04`

### 2.4 mini 阶段要处理多少

我已经把该交给 `gpt-5.2-mini` 的行单独打包出来了：

- 总计：`1354` 行
- `mini-unmatched`: `538`
- `mini-low-forced`: `816`
- 批次数：`12`

这 `1354` 行是 mini 当前要处理的主池。

---

## 3. 当前主线的正确理解

### 3.1 现在不是“从头自动匹配”

自动粗匹配已经做到了 `4620 / 5158`。

所以 mini 不是来重新搭整条 Phase C 的，而是来处理 **剩余未匹配 + 已匹配但明显低分不稳的行**。

### 3.2 现在也不是“逐字精修全量字幕”

当前不是精修全量 `5158` 行。

mini 只处理：

- `538` 条仍然 `unmatched` 的英文 cue
- `816` 条已经粗挂上中文、但 `match_score` 很低的 forced 行

### 3.3 mini 的角色

mini 的角色不是：

- 重写主算法
- 重建时间轴
- 全量重跑 embedding 匹配
- 改变英文 cue 骨架
- 反过来用中文主导结构

mini 的角色是：

1. 对 `unmatched` 行尽量补一个合理中文。
2. 对低分 forced 行判断当前中文是否还能保留。
3. 只在必要时替换成更合理文本。
4. 对实在不靠谱的行明确给 `no_match` 或 `unsure`。

---

## 4. 当前应该读取的文件

### 4.1 主线结果

优先看：

- `scratch\phase_c_english_first_forced_rematch_v7_parttail\manifest.json`
- `scratch\phase_c_english_first_forced_rematch_v7_parttail\all_segments.json`

当前总入口指针：

- `scratch\PHASE_C_CURRENT_BEST.txt`
- `scratch\PHASE_C_CURRENT_MODEL_APPLIED.txt`

### 4.2 mini 队列入口

mini 交接包在：

- `scratch\phase_c_gpt52mini_pack_v1`

核心文件：

- `scratch\phase_c_gpt52mini_pack_v1\manifest.json`
- `scratch\phase_c_gpt52mini_pack_v1\mini_rows.tsv`
- `scratch\phase_c_gpt52mini_pack_v1\mini_rows.jsonl`
- `scratch\phase_c_gpt52mini_pack_v1\screening_prompt.md`
- `scratch\phase_c_gpt52mini_pack_v1\batches\mini_batch_001.jsonl`
- `scratch\phase_c_gpt52mini_pack_v1\batches\mini_batch_002.jsonl`
- `...`
- `scratch\phase_c_gpt52mini_pack_v1\batches\mini_batch_012.jsonl`

---

## 5. 这 `1354` 行到底是什么

### 5.1 `mini-unmatched`

这类行当前没有挂上中文。

它们通常具备这些信息：

- `english_text`
- `english_context_text`
- `estimated_chinese_preview`
- `nearest_prev_matched_text`
- `nearest_next_matched_text`

也就是说，很多并不是“完全没中文可参考”，而是：

- 自动规则还不敢认领
- OCR 片段很脏
- 句子过短
- speaker 容易串
- 多句对多句切分不稳

mini 在这类行上的主要任务是：

- 看能不能基于附近中文预览和前后锚点，补一个 **够用、不过分离谱** 的中文

### 5.2 `mini-low-forced`

这类行已经有当前中文，但分数低。

典型情况是：

- `match_origin = forced-clip-window-v1`
- `match_origin = forced-gap-rescue-v1`
- `match_origin = forced-tail-fill-v1`
- `match_origin = forced-part-tail-fill-v1`
- `match_origin = forced-micro-gap-v1`

它们不一定错，但不稳。

mini 在这类行上的主要任务是：

1. 判断当前 `current_chinese_text` 是否还能保留。
2. 如果明显不对，就替换。
3. 如果附近也看不到靠谱中文，就直接 `no_match`。

---

## 6. mini 必须遵守的总原则

### 6.1 英文骨架优先

永远记住：

- 英文 cue 是唯一骨架
- 中文是往英文上挂
- 不是先拼中文再回头找英文

### 6.2 允许粗糙，但不能明显串句

当前阶段允许：

- 中文不够优美
- OCR 有轻微脏字
- 不是完美逐字翻译

当前阶段不允许：

- 明显串到前一句或后一句
- 明显把别人的台词挂过来
- 明显把战斗口号挂到叙述句上
- 明显把人物对话挂到旁白/说明上

### 6.3 speaker 尽量对齐

如果英文带 speaker，如：

- `Atsu:`
- `Kengo:`
- `Kiku:`

那中文最好也尽量与附近 speaker 保持一致。

如果中文预览里 speaker 明显不对，而语义也对不上，就不要硬挂。

### 6.4 不要发明新剧情

不允许凭空翻译一个完全不存在于附近中文窗口里的长句。

可以做的是：

- 在附近中文明显残缺时做保守修整
- 基于前后上下文判断短句的合理归属

不可以做的是：

- 直接把英文句子完整翻译成全新中文并当成 OCR 匹配结果

也就是说，这一阶段是 **匹配/校正**，不是 **自由翻译重写**。

### 6.5 多余中文可以丢

如果附近中文很多，但对这条英文没有明显对应关系：

- 允许给 `no_match`
- 不要为了提高命中率乱选一条

---

## 7. mini 的输出格式

mini 对每一行应该输出 JSON，格式如下：

```json
{
  "queue_rank": 123,
  "decision": "keep_current_match | replace_match | fill_match | no_match | unsure",
  "confidence": 0.0,
  "suggested_chinese_text": "",
  "reason": ""
}
```

字段含义：

- `queue_rank`
  - 必须原样带回
  - 这是后续回灌的主键之一
- `decision`
  - 只能从固定枚举里选
- `confidence`
  - `0.0 ~ 1.0`
- `suggested_chinese_text`
  - 有替换或补配时填写
  - `keep_current_match` 时通常可留空
- `reason`
  - 简短说明依据，不要长篇大论

---

## 8. 五种决策到底怎么用

### 8.1 `keep_current_match`

适用：

- 当前已有中文
- 虽然分数低，但看起来还能成立
- 周围中文预览和前后锚点没有明显冲突

一般用于：

- `mini-low-forced`

不要用于：

- 当前明显串句
- speaker 明显错
- 中文语义明显是别的句子

### 8.2 `replace_match`

适用：

- 当前已有中文
- 但当前中文明显不对
- 同时附近窗口里能看到更合理的中文

一般用于：

- `mini-low-forced`

### 8.3 `fill_match`

适用：

- 当前是 `unmatched`
- 附近窗口里能找到比较像这句的中文
- 前后锚点支持这个选择

一般用于：

- `mini-unmatched`

### 8.4 `no_match`

适用：

- 附近没有靠谱中文
- 候选都明显不对
- 强挂只会制造脏配

这不是失败。

这表示：

- 当前这句先不配
- 保持英文骨架完整
- 后面如果需要可以再更高级处理

### 8.5 `unsure`

适用：

- 有两个以上候选都像
- 说话人/句意/前后顺序冲突明显
- 你觉得强判风险太大

`unsure` 应该少用，但不要完全禁用。

---

## 9. 推荐的实际判定顺序

对每一行，建议按下面顺序判断：

1. 先看 `review_bucket`
2. 再看 `english_text`
3. 再看 `english_context_text`
4. 再看 `current_chinese_text` 或 `estimated_chinese_preview`
5. 再看 `nearest_prev_matched_text`
6. 再看 `nearest_next_matched_text`
7. 最后给决策

简化成一句话就是：

**先看英文在说什么，再看附近中文里哪一段最像，再用前后锚点确认是不是串行。**

---

## 10. 优先处理顺序

### 10.1 先处理 `mini-unmatched`

因为这部分直接影响覆盖率。

优先级：

1. `mini-unmatched`
2. `mini-low-forced`

### 10.2 再处理 `mini-low-forced`

这部分主要影响脏配率，而不是覆盖率。

如果时间不够，先把 `538` 条 `mini-unmatched` 吃掉，收益最大。

---

## 11. 真实例子：`mini-unmatched`

下面是一条真实 `mini-unmatched`：

```json
{
  "queue_rank": 1,
  "review_bucket": "mini-unmatched",
  "part_name": "ghost-yotei-part01",
  "clip_name": "37336780446-1-192",
  "english_cue_id": "cue_00119",
  "english_text": "Kengo: Excellent!",
  "english_context_text": "Kengo: Trust me. Yone: He's learned from experience. Kengo: Excellent! Kengo: Excellent! Kengo: Don't let him catch you! Jubei: You got lucky!",
  "estimated_chinese_preview": "笃：格挡早会了。 谦吾：我看未必。 谦吾：十兵卫， 谦吾：上 谦吾：上。 米：但别大重 米：但别太重。 谦吾：确实认真听讲了。",
  "nearest_prev_matched_text": "米：都是经验之谈。",
  "nearest_next_matched_text": "谦吾：漂亮！别让他逮着！"
}
```

这个例子里，下一条已匹配是：

- `谦吾：漂亮！别让他逮着！`

英文当前句是：

- `Kengo: Excellent!`

所以新会话里的 mini 要考虑的是：

- 这句是否其实对应“漂亮！”一类短夸奖
- 还是附近没有单独可分出的中文，只能 `no_match`

这里不应该做的事是：

- 看见英文很简单，就自己硬翻“谦吾：漂亮！”
- 如果附近中文窗口并没有可独立支撑这一句，就不能凭空生成

---

## 12. 真实例子：`mini-low-forced`

下面是一条真实 `mini-low-forced`：

```json
{
  "queue_rank": 539,
  "review_bucket": "mini-low-forced",
  "part_name": "ghost-yotei-part01",
  "clip_name": "37336780446-1-192",
  "english_cue_id": "cue_00134",
  "english_text": "Kengo: Begin!",
  "english_context_text": "Atsu: Yes! Finally! Kengo: Whoever lands the most strikes will receive an extra portion of fish for dinner. Kengo: Begin! Jubei: That fish is mine! Atsu: You can lick the bones when I'm done!",
  "match_origin": "forced-clip-window-v1",
  "match_score": 0.1783,
  "current_chinese_text": "谦吾：击中次数多的人晚上多吃条鱼",
  "estimated_chinese_preview": "谦吾：接下来学习时机与耐心。 笃：干嘛看我? 十兵卫：你野马似的耐不住性子。 笃：至少我不臭。 谦吾：专心。 兼吾：专心 谦吾：专心。",
  "nearest_prev_matched_text": "谦吾：，击中次数多的入晚工多吃杀鱼。",
  "nearest_next_matched_text": "十兵卫：鱼是我的！"
}
```

英文是：

- `Kengo: Begin!`

当前中文却是：

- `谦吾：击中次数多的人晚上多吃条鱼`

很明显，这句更像前一句规则说明，而不是“开始”。

所以这类情况大概率不该 `keep_current_match`。

更合理的可能是：

- `replace_match`，如果附近能看到更像“开始 / 上 / 来吧”的中文
- `no_match`，如果附近没有独立可认领文本

---

## 13. 具体决策策略

### 13.1 对 `mini-unmatched`

建议策略偏保守：

- 有明显对应：`fill_match`
- 没有明显对应：`no_match`
- 只有模糊感觉：`unsure`

不要因为想追覆盖率，就把任何附近中文都硬挂上去。

### 13.2 对 `mini-low-forced`

建议策略偏纠错：

- 当前中文还说得通：`keep_current_match`
- 当前中文明显错，但附近有更合理候选：`replace_match`
- 当前中文明显错，附近也没靠谱候选：`no_match`

### 13.3 对特别短的句子

比如：

- `Yes.`
- `Come on!`
- `Good.`
- `There.`
- `Much better.`

这类句子最容易串。

判断时一定要更依赖：

- 前后英文上下文
- 前后中文锚点
- speaker 一致性

### 13.4 对战斗/训练场景

战斗和训练场景常见问题：

- 短句密度高
- 鼓励语重复
- OCR 易脏
- speaker 容易串

所以如果你看到一串：

- “上”
- “漂亮”
- “专心”
- “再来”
- “别让他逮着”

这类都很像，但不意味着每条英文都能精确拆出独立中文。

在这种情况下：

- 宁可 `no_match`
- 不要为了补齐而连续错挂

---

## 14. 新会话里的推荐工作流

### 14.1 开场先读这些

新会话里建议先读：

1. `scratch\PHASE_C_CURRENT_BEST.txt`
2. `scratch\phase_c_english_first_forced_rematch_v7_parttail\manifest.json`
3. `scratch\phase_c_gpt52mini_pack_v1\manifest.json`
4. `scratch\phase_c_gpt52mini_pack_v1\screening_prompt.md`

### 14.2 先从 batch 开始，不要全量一起吞

建议按 batch 处理：

- `mini_batch_001.jsonl`
- `mini_batch_002.jsonl`
- `...`

每次一批，便于观察 mini 的稳定性。

### 14.3 先吃 `mini-unmatched`

如果要先做高收益任务，建议：

1. 先按 `review_bucket = mini-unmatched` 处理
2. 再处理 `mini-low-forced`

### 14.4 每次输出保持结构化

建议每批都输出 JSONL 或 TSV，至少保留：

- `queue_rank`
- `decision`
- `confidence`
- `suggested_chinese_text`
- `reason`

不要只给自然语言总结。

---

## 15. mini 不应该做什么

### 15.1 不要改主线统计口径

不要在新会话里把主线重新定义成：

- 中文骨架优先
- 以 no-match 闭合为目标
- 重建全新时间轴

### 15.2 不要碰旧 complete 分支当主入口

不要把下面这些再当主结果继续扩展：

- `phase_c_predecision_applied_v3_complete`
- `phase_c_master_delivery_v1_complete`
- `phase_c_release_snapshot_v1_complete`

它们是旧分支的完工包装，不是当前 rematch 主线。

### 15.3 不要无依据地自由翻译

这一点非常关键。

mini 现在做的是：

- 匹配
- 替换
- 补配
- 清错

不是：

- 看英文后直接生成一条全新翻译字幕

### 15.4 不要提前做时间轴重校

当前时间轴已经由英文 cue 骨架提供。

新会话里不要先做：

- 重新切时间
- 合并/拆分英语 cue
- 大规模改 start/end

后面真要做时间轴，是下一阶段。

---

## 16. 当前最重要的数字关系

这是新会话最容易混淆的地方。

### 16.1 `4620`

表示：

- 当前主线里已经挂上中文的英文 cue 数

### 16.2 `538`

表示：

- 当前主线里仍是 `unmatched` 的 cue 数

### 16.3 `816`

表示：

- 当前已挂上中文，但低分 forced、值得 mini 复核的 cue 数

### 16.4 `1354`

表示：

- 当前 mini 总处理池
- 即 `538 + 816`

---

## 17. 给新会话的推荐开场词

下面这段可以直接给新会话：

```text
请接手 Ghost Yotei Phase C 的 gpt-5.2-mini 精修阶段。

主线不是旧的 no-match complete 分支，而是英文骨架优先的 rematch 主线：
scratch\phase_c_english_first_forced_rematch_v7_parttail

当前状态：
- total english cues: 5158
- matched: 4620
- unmatched: 538
- low-forced review rows: 816
- mini total queue: 1354

你的任务不是重建主算法，也不是重做时间轴，而是：
1. 对 mini-unmatched 尽量 fill_match
2. 对 mini-low-forced 判断 keep_current_match / replace_match / no_match
3. 保持英文骨架优先
4. 不要凭空自由翻译

先读：
- scratch\PHASE_C_CURRENT_BEST.txt
- scratch\phase_c_english_first_forced_rematch_v7_parttail\manifest.json
- scratch\phase_c_gpt52mini_pack_v1\manifest.json
- scratch\phase_c_gpt52mini_pack_v1\screening_prompt.md

然后从：
- scratch\phase_c_gpt52mini_pack_v1\batches

开始分批处理。
```

---

## 18. 最后一句话总结

当前真正的下一步不是再做包装，也不是再跑旧的 request 压缩链，而是：

**让 `gpt-5.2-mini` 接手这 `1354` 行，对当前 `89.57%` 覆盖率做定点补配和纠错。**

这份文档就是为这一步准备的。
