# Ghost Yotei Phase C 现状总文档与模型流水线操作说明

## 1. 这份文档的定位

这是一份给“人类操作者”看的总说明文档。

它解决的不是单一脚本怎么跑，而是把 **Phase C 当前真实现状、关键数字、目录入口、自动链路、模型链路、重试链路、产物边界、Git 提交边界** 一次讲清楚。

如果后面要新开对话、换操作者、或者临时停下来几天后再继续，优先先读这份文档。

---

## 2. 先给结论

当前项目的真实状态不是“快做完了”，也不是“完全没进展”。

更准确的描述是：

1. **完整轨骨架已经建立完成。**
2. **高质量自动匹配已经有一版稳定基线。**
3. **真正的瓶颈已经从“搭框架”转成“还剩大量句子需要判断”。**
4. **为了解决这个问题，已经把模型外呼链路压缩到相对可跑的规模。**

当前最核心的四组数字如下：

### 2.1 Phase C 稳定自动基线

- 英文总 cue：`5158`
- 当前自动已匹配：`1602`
- 当前自动未匹配：`3556`
- 当前稳定自动覆盖率：`31.06%`

### 2.2 模型筛查原始总池

这不是自动匹配结果，而是“需要交给模型进一步判断的 review row 总池”。

- 原始筛查总池：`4506`

这个数字为什么不是 `3556`，后面会详细解释。

### 2.3 经过 speaker 规则瘦身后的模型 review 池

- 瘦身前：`4506`
- speaker-trim 后：`4280`
- 自动剔除：`226`
  - `206` 条自动 keep
  - `20` 条自动 reject

### 2.4 当前模型请求根的请求数

当前模型不是一行一个请求，而是多行打包请求。

- 最早一行一请求：`4506` 个请求
- 当前主线请求根：`349` 个请求

这意味着：

- “还差几千句”这件事依然成立
- 但“要打给模型的请求数”已经被压缩到 `349`

这两件事 **同时成立**，而且 **并不矛盾**

---

## 3. 最重要的纠偏：4 组数字分别代表什么

这是最容易混淆的地方。

### 3.1 `1602 / 5158`

这是 **Phase C 自动构建后的当前双语轨命中结果**。

含义是：

- 一共有 `5158` 条英文 cue
- 当前自动流程已经给其中 `1602` 条挂上了中文结果
- 还剩 `3556` 条没有自动命中

这个数字回答的是：

**“完整双语轨自动重建到了什么程度？”**

### 3.2 `3556`

这表示：

**当前自动双语轨里仍然 `unmatched` 的英文 cue 数量。**

注意：

这不是“还要喂给模型的请求数”，只是“当前轨道里还没自动挂上中文的英文行数”。

### 3.3 `4506`

这是：

**模型 review 原始总池的行数。**

它不是单纯等于 `3556`，因为它包含两大类：

1. `match_fix`
   - 已经自动匹配上了，但匹配可能有错
   - 这部分要让模型做“纠错判断”

2. `unmatched`
   - 还没匹配上
   - 这部分要让模型做“补配判断”

所以：

- `3556` 是自动轨里的未命中数
- `4506` 是模型总 review 行数

之所以 `4506 > 3556`，就是因为里面还包含了大量“已命中但可能错”的 `match_fix` 行。

### 3.4 `349`

这是：

**当前最新模型请求根里的实际请求数**

它不等于 review 行数，是因为已经做了多层压缩：

1. 先从 `4506` 行筛出 speaker-trim 后的 `4280`
2. 再把多条 row 打包到同一个请求里
3. 再按不同队列用不同参数装箱

最终压成了：

- `349` 个模型请求

这就是“几千句还没做完”与“请求数已经不算太大”能同时成立的原因。

---

## 4. 当前稳定官方基线在哪里

当前稳定自动基线不是最新实验版，而是下面这一版：

### 4.1 当前 Phase C 推荐输出

`scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2`

### 4.2 当前推荐指针

`scratch/PHASE_C_CURRENT_BEST.txt`

### 4.3 当前基线 manifest

`scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2/manifest.json`

### 4.4 当前稳定基线关键数字

- 总英文 cue：`5158`
- matched：`1602`
- unmatched：`3556`
- coverage：`0.3106`

分 part：

- `part01 = 402 / 1249 = 32.19%`
- `part02 = 411 / 1444 = 28.46%`
- `part03 = 422 / 1354 = 31.17%`
- `part04 = 367 / 1111 = 33.03%`

### 4.5 当前稳定基线的意义

这版不是终点，但它是当前“可继续叠模型结果”的稳定底座。

也就是说：

- 后续模型纠错
- 模型补配
- retry 回流
- delta 对比
- burn-in 预备

都应该以它为 Phase C base。

---

## 5. 当前模型链路的真实主线是什么

当前主线已经不是早期的单行请求版，也不是旧的 `v3_grouped`、`v4_turbo8`、`v6_adaptive12_b6000`。

当前最新主线是：

### 5.1 当前模型请求指针

`scratch/PHASE_C_CURRENT_MODEL_REQUESTS.txt`

当前内容是：

1. `scratch/phase_c_model_request_batches_v8_mixedfast_speakertrim`
2. `first_pass_match_fix`

### 5.2 当前请求根

`scratch/phase_c_model_request_batches_v8_mixedfast_speakertrim`

### 5.3 上游 speaker-trim 筛查包

`scratch/phase_c_llm_screening_pack_v6_speakertrim`

### 5.4 当前打包 profile

`scratch/phase_c_model_request_profiles_v1/mixedfast_7500.json`

### 5.5 当前建包器

`tools/build_phase_c_model_request_root.py`

---

## 6. 当前模型请求根的四条队列

当前不是一股脑全部一起跑，而是拆成四条队列：

1. `first_pass_match_fix`
2. `remaining_match_fix`
3. `unmatched_rich`
4. `unmatched_rest`

### 6.1 当前各队列请求数

在 `scratch/phase_c_model_request_batches_v8_mixedfast_speakertrim/manifest.json` 里：

- `first_pass_match_fix = 58`
- `remaining_match_fix = 19`
- `unmatched_rich = 267`
- `unmatched_rest = 5`

合计：

- `349` 个请求

### 6.2 每个队列的角色

#### `first_pass_match_fix`

这是第一批最值得先跑的。

含义是：

- 当前自动已经匹配上了
- 但这批很可疑
- 模型更适合先做“纠错”

为什么优先：

- 它的价值密度最高
- 很多是明显跨 clip 错配
- 纠正后能快速清理脏结果

#### `remaining_match_fix`

这是第二层纠错队列。

和第一批相比：

- 仍然属于“已匹配但可能错”
- 只是优先级没那么高

#### `unmatched_rich`

这是最大的一池。

它的特点是：

- 当前还没匹配上
- 但上下文、预览信息相对更丰富
- 更适合模型尝试补配

#### `unmatched_rest`

这是最后那点边角。

- 数量很少
- 信息价值也相对较低

---

## 7. 为什么要先做 speaker-trim

这是当前加速里最关键的一步之一。

### 7.1 原问题

如果什么都不裁，模型会看到大量其实并不值得它判断的行：

- 一些 speaker 非常明确、而且当前匹配本来就对
- 一些 speaker 非常明确、而且当前匹配明显错

这类行继续交给模型，其实是在浪费请求预算。

### 7.2 当前的保守 speaker 规则

当前不是胡乱做 NER，也不是全自动替换整条字幕。

而是只做非常保守的一层：

- 如果英文 speaker 和当前中文 speaker 的映射非常稳定，且当前不跨 clip，自动 keep
- 如果英文 speaker 和当前中文 speaker 明显冲突，且当前跨 clip，自动 reject

### 7.3 当前使用的安全 speaker 集

当前主要用了这些高确定映射：

- `Atsu -> 笃`
- `Oyuki -> 阿雪`
- `Jubei -> 十兵卫`
- `Kiku -> 菊`
- `Kengo -> 谦吾`
- `Yone -> 米`
- `Hanbei -> 半兵卫`
- `Mad Goro -> 疯五郎`
- `Lord Saito -> 斋藤`
- `Master Yoshida -> 枪术师父`
- `The Oni -> 恶鬼`
- `Oni Raider -> 鬼面队`
- `Saito Outlaw -> 斋藤匪徒`

### 7.4 当前 speaker-trim 的实际收益

来自：

`scratch/phase_c_llm_screening_pack_v6_speakertrim/manifest.json`

结果是：

- 原 review rows：`4506`
- trim 后：`4280`
- 自动 keep：`206`
- 自动 reject：`20`

按队列看：

- `first_pass_match_fix: 592 -> 581`
- `remaining_match_fix: 401 -> 186`
- `unmatched_rich: 3446 -> 3446`
- `unmatched_rest: 67 -> 67`

也就是说：

这一步最有效砍掉的是 `remaining_match_fix`。

这很合理，因为它本来就含有大量“已有当前中文匹配”的行，speaker 信息最容易直接判。

### 7.5 speaker-trim 产物入口

- 总表：`scratch/phase_c_llm_screening_pack_v6_speakertrim/manifest.json`
- 摘要：`scratch/phase_c_llm_screening_pack_v6_speakertrim/queue_summary.tsv`
- 自动决策明细：`scratch/phase_c_llm_screening_pack_v6_speakertrim/auto_decisions.tsv`

---

## 8. 为什么请求数能从 4506 压到 349

这不是一步做到的，而是多轮演进的结果。

### 8.1 初始阶段：一行一请求

最早是：

- 每一条 review row 生成一个模型请求
- 请求数直接等于 review 行数

结果：

- `4506 rows = 4506 requests`

这显然太慢。

### 8.2 第一轮：compact prompt

做了两件事：

1. 缩短提示词
2. 缩短上下文和 preview

结果：

- 单请求字符数明显下降
- 但请求数还没本质减少

### 8.3 第二轮：grouped request

开始一次请求带多行：

- `rows_per_request > 1`

这时请求数从几千掉到千级。

### 8.4 第三轮：turbo8

固定打成 `8 rows/request`

结果：

- 请求数掉到 `565`

### 8.5 第四轮：adaptive shared profile

不再固定 8 行，而是：

- 上限 `12 rows/request`
- 用字符预算 `6000` 控制单请求体积

结果：

- 请求数 `565 -> 465`

### 8.6 第五轮：mixedfast queue-specific profile

不同队列用不同参数：

- `first_pass_match_fix / remaining_match_fix` 更保守
- `unmatched_rich / unmatched_rest` 更激进

结果：

- 请求数 `465 -> 372`

### 8.7 第六轮：speakertrim + mixedfast

先把一批明显不用模型判断的行从 review 池裁掉，再做 queue-specific grouped build。

结果：

- review rows `4506 -> 4280`
- requests `372 -> 349`

### 8.8 当前请求根的具体参数

#### `first_pass_match_fix`

- `rows_per_request = 14`
- `max_request_char_budget = 7000`

#### `remaining_match_fix`

- `rows_per_request = 14`
- `max_request_char_budget = 7000`

#### `unmatched_rich`

- `rows_per_request = 16`
- `max_request_char_budget = 7500`

#### `unmatched_rest`

- `rows_per_request = 16`
- `max_request_char_budget = 7500`

公共参数：

- `prompt_style = compact`
- `preview_char_limit = 100`
- `context_char_limit = 80`

---

## 9. 当前已经打通的整条模型闭环

当前不是只有“请求包”。

整条链已经闭环到：

1. screening pack
2. request batches
3. response ingest
4. merge plan
5. apply 回写到 Phase C
6. delta pack
7. burn-in prep
8. retry queue
9. handoff / iteration

下面逐段说明。

### 9.1 Screening pack

相关目录：

- `scratch/phase_c_llm_screening_pack_v5`
- `scratch/phase_c_llm_screening_pack_v6_speakertrim`

相关脚本：

- `tools/export_phase_c_llm_screening_pack.py`
- `tools/refine_phase_c_llm_screening_pack.py`
- `tools/specialize_phase_c_llm_screening_pack.py`
- `tools/tier_phase_c_llm_screening_pack.py`
- `tools/focus_phase_c_llm_screening_pack.py`
- `tools/refine_phase_c_llm_screening_pack_speaker_rules.py`

### 9.2 Request batches

当前主入口：

- `scratch/phase_c_model_request_batches_v8_mixedfast_speakertrim`

相关脚本：

- `tools/build_phase_c_model_request_batches.py`
- `tools/build_phase_c_model_request_root.py`

### 9.3 Response ingest

脚本：

- `tools/ingest_phase_c_model_responses.py`

功能：

- 读模型 JSONL 回包
- 对齐 `custom_id`
- 支持 grouped rows 结构
- 写出 `normalized_responses.tsv`
- 写出 `unresolved_responses.tsv`
- 写出 `missing_requests.tsv`

### 9.4 Merge plan

脚本：

- `tools/build_phase_c_model_merge_plan.py`

功能：

- 汇总多个队列的 ingest 结果
- 对同一英文 cue 去重
- 重试轮覆盖首轮
- 生成统一动作表

动作类型包括：

- `keep-existing`
- `clear-existing`
- `replace-with-suggested-text`
- `fill-with-suggested-text`
- `manual-review`

### 9.5 Apply 回写

脚本：

- `tools/apply_phase_c_model_merge_plan.py`

功能：

- 把 merge plan 回写到当前 Phase C 基线
- 写出新的 `all_segments.json / tsv`
- 写出 `part01..04/*.draft.json|tsv|srt`
- 写出 `applied_actions.tsv`
- 写出 `skipped_actions.tsv`

### 9.6 Delta pack

脚本：

- `tools/build_phase_c_model_delta_pack.py`

功能：

- 比较应用前后的差异
- 统计净变化

### 9.7 Burn-in prep

脚本：

- `tools/export_phase_c_burnin_prep.py`

功能：

- 生成 bilingual srt
- 生成现成 ffmpeg 命令
- 为后续烧录做准备

### 9.8 Retry queue

脚本：

- `tools/build_phase_c_model_retry_batches.py`

功能：

- 从 ingest 结果里抽出需要重试的残差
- 自动命名 `retry_roundN -> retry_round{N+1}`
- 支持 grouped request index

### 9.9 Handoff / iteration

脚本：

- `tools/build_phase_c_model_handoff.py`
- `tools/advance_phase_c_model_iteration.py`
- `tools/run_phase_c_model_postprocess.py`

功能：

- 一轮处理完成后自动产出 handoff
- 自动长出下一轮 retry
- 更新当前指针

---

## 10. 当前已经验证过的关键能力

这部分很重要，因为“脚本存在”不等于“真的跑通过”。

当前已经验证过：

### 10.1 grouped response ingest

验证结果：

- grouped response 可以正确拆回单行 normalized rows

### 10.2 grouped retry generation

验证结果：

- grouped 请求根生成 `retry_round1` 已经跑通
- `request_custom_id` / `row_id` 能正确保留

### 10.3 adaptive shared-profile ingest/retry

验证结果：

- `v6_adaptive12_b6000` 的 ingest 和 retry 都跑通过

### 10.4 mixedfast ingest/retry

验证结果：

- `v7_mixedfast_7500` 的 ingest 和 retry 都跑通过

### 10.5 speakertrim mixedfast ingest/retry

验证结果：

- `v8_mixedfast_speakertrim` 的 ingest 和 retry 也跑通过

相关 smoke 目录包括：

- `scratch/phase_c_speakertrim_smoke_ingest`
- `scratch/phase_c_speakertrim_retry_smoke_v2`

---

## 11. 当前真正还剩下什么工作

真正没完成的，不是“写脚本”，而是“把海量残余句子真正判断掉”。

### 11.1 自动匹配层面

当前仍有：

- `3556` 条英文 cue 没自动挂上中文

### 11.2 模型判断层面

当前 speaker-trim 后仍有：

- `4280` 条 review rows

### 11.3 请求层面

当前已经压到：

- `349` 个模型请求

所以目前的现实是：

- 自动基线还不够高
- 但模型链路已经具备生产条件
- 接下来真正该做的是 **跑模型，不是再反复搭框架**

---

## 12. 当前最应该怎么跑

### 12.1 跑批顺序

推荐顺序仍然是：

1. `first_pass_match_fix`
2. `remaining_match_fix`
3. `unmatched_rich`
4. `unmatched_rest`

### 12.2 为什么不是先跑 unmatched

因为：

- `match_fix` 更值钱
- 这批本来就在当前轨里
- 一旦纠正，会直接清理脏结果
- 比盲目补配更容易快速拉高有效质量

### 12.3 当前第一刀该跑什么

当前就是：

- `scratch/phase_c_model_request_batches_v8_mixedfast_speakertrim/first_pass_match_fix`

它只有：

- `58` 个请求

---

## 13. 推荐日常操作命令

下面给最实用的命令，不讲花活。

### 13.1 查看当前主请求根

```powershell
Get-Content scratch\PHASE_C_CURRENT_MODEL_REQUESTS.txt
```

### 13.2 只跑某一队列的模型回灌

假设你刚跑完 `first_pass_match_fix`，响应都放在：

`YOUR_RESPONSE_DIR`

则：

```powershell
python tools/ingest_phase_c_model_responses.py `
  --request-root scratch\phase_c_model_request_batches_v8_mixedfast_speakertrim `
  --queue-name first_pass_match_fix `
  --response-dir YOUR_RESPONSE_DIR `
  --output-dir scratch\phase_c_model_response_ingest_v1
```

### 13.3 跑整条后处理链

如果你的响应根目录长这样：

- `YOUR_RESPONSE_ROOT/first_pass_match_fix/*.jsonl`
- `YOUR_RESPONSE_ROOT/remaining_match_fix/*.jsonl`
- `YOUR_RESPONSE_ROOT/unmatched_rich/*.jsonl`
- `YOUR_RESPONSE_ROOT/unmatched_rest/*.jsonl`

则直接：

```powershell
python tools/run_phase_c_model_postprocess.py `
  --response-root YOUR_RESPONSE_ROOT `
  --ingest-root scratch\phase_c_model_response_ingest_v1 `
  --merge-plan-dir scratch\phase_c_model_merge_plan_v1 `
  --phase-c-json scratch\phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2\all_segments.json `
  --applied-output-dir scratch\phase_c_model_applied_v1 `
  --delta-output-dir scratch\phase_c_model_delta_pack_v1 `
  --burnin-output-dir scratch\phase_c_burnin_prep_v1 `
  --parts-root scratch `
  --next-retry-output-dir scratch\phase_c_model_retry_batches_v1 `
  --next-retry-skip-missing `
  --update-current-pointers
```

### 13.4 最省事的一轮推进命令

如果当前指针已经正确，就直接：

```powershell
python tools/advance_phase_c_model_iteration.py `
  --response-root YOUR_RESPONSE_ROOT `
  --next-retry-skip-missing `
  --update-current-pointers
```

### 13.5 单独构建 speaker-trim 筛查包

```powershell
python tools/refine_phase_c_llm_screening_pack_speaker_rules.py `
  --input-dir scratch\phase_c_llm_screening_pack_v5 `
  --output-dir scratch\phase_c_llm_screening_pack_v6_speakertrim
```

### 13.6 单独构建 queue-specific request root

```powershell
python tools/build_phase_c_model_request_root.py `
  --input-dir scratch\phase_c_llm_screening_pack_v6_speakertrim `
  --profile-json scratch\phase_c_model_request_profiles_v1\mixedfast_7500.json `
  --output-dir scratch\phase_c_model_request_batches_v8_mixedfast_speakertrim `
  --batch-size 150
```

---

## 14. 当前目录速查

### 14.1 Phase C 自动基线

- `scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2`

### 14.2 当前模型请求指针

- `scratch/PHASE_C_CURRENT_MODEL_REQUESTS.txt`

### 14.3 当前模型请求根

- `scratch/phase_c_model_request_batches_v8_mixedfast_speakertrim`

### 14.4 当前 speaker-trim 筛查包

- `scratch/phase_c_llm_screening_pack_v6_speakertrim`

### 14.5 当前 request profile

- `scratch/phase_c_model_request_profiles_v1/mixedfast_7500.json`

### 14.6 当前模型 runbook

- `scratch/phase_c_model_request_batches_v1/RUNBOOK.md`

### 14.7 当前最佳 Phase C 指针

- `scratch/PHASE_C_CURRENT_BEST.txt`

### 14.8 当前模型 handoff 指针

- `scratch/PHASE_C_CURRENT_MODEL_HANDOFF.txt`

### 14.9 当前模型 applied 指针

- `scratch/PHASE_C_CURRENT_MODEL_APPLIED.txt`

### 14.10 当前 retry 请求指针

- `scratch/PHASE_C_CURRENT_MODEL_RETRY_REQUESTS.txt`

---

## 15. 当前还存在的边界和风险

### 15.1 自动基线覆盖率仍然只有 31.06%

这说明：

- 当前自动规则和 embedding 只能打到这个水平
- 后续必须依赖模型补判，或者再投入更重的算法重构

### 15.2 `unmatched_rich` 仍然是最大头

即使 speaker-trim 很有效，它也主要打掉 `match_fix`

而：

- `unmatched_rich = 3446 rows`
- 打包后仍占 `267 requests`

这依然是当前最大工作量来源。

### 15.3 当前 speaker-trim 是保守规则，不是最终语义判断

它适合：

- 明显 speaker 一致
- 明显 speaker 冲突

它不适合：

- 泛称人物
- 省略主语
- 多说话人挤在一起
- OCR 标签脏乱

所以 speaker-trim 只是“减负”，不是终局。

### 15.4 代码和 scratch 产物非常多，Git 不能乱推

当前仓库有大量：

- 工具脚本
- scratch 目录产物
- OCR / SRT / draft / json
- 模型中间件结果

这些东西不能在“只推文档”的提交里混进去。

---

## 16. 只推文档时的 Git 边界

这是当前必须严格执行的规则。

### 16.1 本次允许提交的内容

只允许提交：

- `docs/**/*.md`

### 16.2 本次明确不能提交的内容

不能提交：

- `scratch/**`
- `tools/**`
- `scripts/**`
- 任何 OCR JSON / SRT / draft / burn-in 产物
- 任何视频
- 任何字幕视频产物
- 任何模型回包

### 16.3 实操原则

即使仓库里已经有很多未跟踪文件，本次也只手工 `git add` 指定的文档文件。

不能用：

- `git add .`
- `git add docs/phase_b`

因为这样很容易把别的文档或别的目录一起带进去。

应该用：

```powershell
git add -- docs/phase_b/你这次新增的那一份文档.md
```

必要时先用：

```powershell
git diff --cached --name-only
```

确认暂存区里真的只有文档。

---

## 17. 当前最推荐的人类操作顺序

如果从现在开始继续推进，推荐顺序是：

1. 先确认 `PHASE_C_CURRENT_MODEL_REQUESTS.txt` 仍指向 `v8_mixedfast_speakertrim`
2. 先跑 `first_pass_match_fix`
3. 回灌、merge、apply、delta、retry
4. 再跑 `remaining_match_fix`
5. 最后再去清 `unmatched_rich`

如果只是要做管理和交接：

1. 看本文件
2. 看 `scratch/phase_c_model_request_batches_v1/RUNBOOK.md`
3. 看 `scratch/PHASE_C_CURRENT_BEST.txt`
4. 看 `scratch/PHASE_C_CURRENT_MODEL_REQUESTS.txt`

这样就足够恢复上下文。

---

## 18. 一句话总结

当前 Phase C 不是没进展，而是已经把“几千句规模的问题”压缩成了：

- 自动基线 `1602 / 5158`
- 模型 review 行 `4280`
- 实际模型请求 `349`

也就是说：

**真正剩下的主要问题已经不是“怎么搭框架”，而是“把这 349 个模型请求尽快跑完并回灌”。**
