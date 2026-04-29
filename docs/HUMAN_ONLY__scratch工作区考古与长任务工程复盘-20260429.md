# scratch 工作区考古与长任务工程复盘

日期：2026-04-29

对象目录：`C:\Users\汪家俊\anime\AnimeTranscoder\scratch`

结论先行：

`scratch` 不是完全没有价值。它确实堆了大量可以清理的重资产，尤其是已经上传到 B 站的硬字幕视频、对白剪辑视频、工作音频和截图。但它也保留了一个很完整的长任务工程轨迹：从音频/视频裁切、英文 OCR、中文 OCR、Phase B 人工确认包、Phase C 全量字幕主线、模型请求批次、模型响应 ingest、质量复查、时间轴导出、字幕烧录、封面制作，到最终发布前 spot check。

如果只从“文件能不能继续直接用”看，很多目录确实可以删。

但如果从“这个项目教会了什么”看，`scratch` 是一份很好的失败与迭代记录。

这篇文档的目的不是保留 `scratch` 本身，而是把里面有学习价值的结构提炼出来。提炼完以后，真正应该长期保留的是这篇复盘、正式脚本、少量 manifest、少量 README、最终版本指针；不是几十 GB 的视频和一堆中间目录。

## 1. 我在 scratch 里看到了什么

顶层目录非常多，但可以归成几类。

### 1.1 视频/音频重资产

这些是真正占空间的东西：

- `scratch/phase_c_hardsub_v36`
- `scratch/ghost-yotei-part01`
- `scratch/ghost-yotei-part02`
- `scratch/ghost-yotei-part03`
- `scratch/ghost-yotei-part04`
- `scratch/yotei`
- `scratch/english_ocr_bench`
- `scratch/sample`
- `scratch/subtitle_position_probe_v1`
- `scratch/bilibili_covers_v1`

实际体积大致是：

| 目录 | 体积 | 主要内容 |
| --- | ---: | --- |
| `phase_c_hardsub_v36` | 约 `52.78 GB` | 最终硬字幕 MP4 输出 |
| `ghost-yotei-part03` | 约 `9.57 GB` | 分段视频/音频/Whisper 中间产物 |
| `ghost-yotei-part01` | 约 `7.95 GB` | 分段视频/音频/Whisper 中间产物 |
| `ghost-yotei-part04` | 约 `7.52 GB` | 分段视频/音频/Whisper 中间产物 |
| `ghost-yotei-part02` | 约 `4.57 GB` | 分段视频/音频/Whisper 中间产物 |
| `yotei` | 约 `2.57 GB` | 早期整段或样片转录工作目录 |
| `english_ocr_bench` | 约 `0.35 GB` | 英文 OCR benchmark 视频和结果 |
| `phase_b_archive` | 约 `0.35 GB` | Phase B 历史归档 |

最重的单项是最终硬字幕视频：

| 文件 | 体积 |
| --- | ---: |
| `scratch/phase_c_hardsub_v36/part01/part01.hardsub.mp4` | 约 `17.77 GB` |
| `scratch/phase_c_hardsub_v36/part02/part02.hardsub.mp4` | 约 `14.43 GB` |
| `scratch/phase_c_hardsub_v36/part03/part03.hardsub.mp4` | 约 `10.80 GB` |
| `scratch/phase_c_hardsub_v36/part04/part04.hardsub.mp4` | 约 `9.77 GB` |

这些如果已经上传并确认不再需要本地重传，技术上最适合清理。

### 1.2 指针文件

顶层有一些非常有价值的小文件：

- `PHASE_B_CURRENT_OFFICIAL_VERSION.txt`
- `PHASE_C_CURRENT_BEST.txt`
- `PHASE_C_CURRENT_MODEL_APPLIED.txt`
- `PHASE_C_CURRENT_MODEL_HANDOFF.txt`
- `PHASE_C_CURRENT_MODEL_REQUESTS.txt`
- `PHASE_C_CURRENT_MODEL_RETRY_REQUESTS.txt`
- `PHASE_C_CURRENT_REVIEW_QUEUE.txt`

这些文件体积几乎为零，但价值很高。

它们告诉后来的人：

- 当前官方 Phase B 是哪一版。
- 当前 Phase C 主线是哪一版。
- 哪个模型输出已应用。
- 哪个请求包是当前模型请求。
- 哪个 review queue 是当前人工或模型复查入口。

如果没有这些指针，`scratch` 会变成一片版本坟场：你只能看到几十个 `v1`、`v2`、`v14`、`v36`，但不知道哪个才是当前可信路径。

### 1.3 Phase B 目录

Phase B 相关目录包括：

- `phase_b_master_reviewed_v6` 到 `phase_b_master_reviewed_v14_round8`
- `phase_b_final_export_v6_medium1` 到 `phase_b_final_export_v14_round8`
- `phase_b_release_v6_frozen` 到 `phase_b_release_v14_round8_frozen`
- `phase_b_context_round*`
- `phase_b_review_patch_round*`
- `phase_b_round*_optimization_pack*`

这些目录说明 Phase B 是一个“人工审核闭环”。

最终官方版本是：

- reviewed master：`scratch/phase_b_master_reviewed_v14_round8`
- final export：`scratch/phase_b_final_export_v14_round8`
- frozen snapshot：`scratch/phase_b_release_v14_round8_frozen`

`phase_b_release_v14_round8_frozen/README.md` 里有明确总结：

- 总段落数：`141`
- `part01`: `33`
- `part02`: `46`
- `part03`: `37`
- `part04`: `25`
- review status：`confirmed = 141`
- 人工确认比例：`141 / 141 = 100%`

这说明 Phase B 的交付哲学是：

> 少量、高置信、人工确认，宁愿范围小，也要闭环硬。

### 1.4 Phase C 目录

Phase C 目录数量最多，说明它是整个项目最复杂的一段。

它包括：

- fulltrack rebuild
- English-first forced rematch
- LLM screening pack
- model request batches
- local model response generation
- ingest
- merge
- applied
- handoff
- review report
- timeaxis export
- burnin prep
- hardsub render
- portal/dashboard/delivery/release snapshot

Phase C 的目标比 Phase B 更野心大：

> 从 141 条人工确认段落，扩展到 5000 多条全片英文 cue 骨架，并尽量补上中文。

这就把问题从“做少量正确字幕”变成了“做全量粗字幕，并控制错误扩散”。

这两种任务完全不同。

## 2. Phase B 教会的东西

Phase B 的核心价值是“闭环”。

它的结构非常值得学习。

### 2.1 小范围人工确认比大范围自动覆盖可靠

Phase B 最终只有 `141` 条，但全部 confirmed。

这看起来数量少，但它有几个优点：

1. 每条都被人看过。
2. 每条都有明确 review status。
3. 每轮 patch 都有上下文包和 review patch。
4. 最终有 frozen snapshot。
5. 可以作为 gold set 或参考锚点。

在字幕工程里，141 条高质量样本比 5000 条不确定样本更适合做“可信基准”。

后面的 Phase C 如果没有 Phase B 这种小规模确认集，就很容易被 coverage 指标带偏。

### 2.2 frozen snapshot 是长期任务必须有的东西

`phase_b_release_v14_round8_frozen` 的价值不是文件多，而是它回答了一个问题：

> 到底哪一版算正式？

长任务最怕版本漂移。

今天觉得 v10 好，明天跑出 v12，后天又手工修 v14。如果没有 freeze，后来的人根本不知道哪个目录能信。

freeze snapshot 至少应该包含：

- 当前正式输入。
- 当前正式输出。
- 上一版正式输出。
- 统计摘要。
- 版本号。
- 确认状态。

Phase B 做对了这一点。

### 2.3 review patch 的目录结构是可复用模式

Phase B 里有很多：

- `phase_b_context_round*_...`
- `phase_b_review_patch_round*_...`
- `phase_b_round*_optimization_pack_*`

这说明它不是直接在大文件里乱改，而是把问题拆成 review batch：

1. 先找候选问题。
2. 导出上下文包。
3. 对上下文做 review。
4. 生成 patch。
5. merge 回 master。
6. 再导出下一轮。

这是一种很稳的长任务编辑模式。

它适合字幕、翻译、OCR 修正、数据清洗，也适合任何“模型能提建议但不能直接信”的场景。

## 3. Phase C 教会的东西

Phase C 的价值更复杂，因为它同时包含成功和风险。

### 3.1 English-first skeleton 是正确的主轴

`PHASE_C_CURRENT_BEST.txt` 里写得很清楚：

- keep all `5158` English cues as the only skeleton
- attach Chinese when a rough match is available
- drop extra Chinese when not needed
- do timeline correction later from English timings

这个决策是合理的。

原因：

1. 英文硬字幕 cue 更接近最终视频时间轴。
2. 如果中文 OCR 质量不稳定，不能让中文 OCR 决定主时间轴。
3. 全片输出需要稳定骨架，否则后面烧录会乱。
4. 中文可以作为附着内容，而不是结构主轴。

这条原则可以抽象成：

> 当两个信号源质量不一致时，让更稳定的信号源负责结构，让较弱信号源只提供内容补充。

在这个项目里：

- 英文 OCR / 英文 cue：结构信号。
- 中文 OCR / 中文候选：内容信号。

### 3.2 coverage ratio 是必要指标，但不是质量指标

Phase C 里出现了几个很有教育意义的 coverage 状态。

早期 complete branch：

- total cues：`5158`
- matched cues：`1582`
- unmatched cues：`3576`
- coverage ratio：`0.3067`

aggressive rematch branch：

- total english cues：`5158`
- current matched cues：`4620`
- coverage ratio：`0.8957`
- remaining unmatched：`538`

最终 `phase_c_model_applied_v36`：

- total English cues：`5153`
- matched cues：`5153`
- coverage ratio：`1.0`
- deleted rows：`3`

这些数字非常有启发。

从 `0.3067` 到 `0.8957` 到 `1.0`，覆盖率一直在变好。

但这不等于质量一直变好。

`phase_c_review_report_v5` 同时指出，虽然已经删除了没有可用中文的 3 行，但仍有 mixed-language contamination：

- `Lord Kitamori-Oni Raiders`
- `Yari`
- `Bo-hiya`
- `Lady Oyuki`
- `Ped Crane Inn`
- `vou`
- `ONRY`

这说明：

> coverage=1.0 只能说明每个英文 cue 都有了某种中文字段，不能说明中文字段自然、准确、无 OCR 噪声。

这是整个项目最重要的教训之一。

### 3.3 “完整”有两种：结构完整和质量完整

Phase C 最终可以做到结构完整：

- 每个 English cue 都有时间轴。
- 每个 cue 都有可输出字段。
- 每个 part 都能导出 SRT。
- 每个 part 都能烧录成视频。

但质量完整是另一回事：

- 中文是否准确。
- OCR 噪声是否清掉。
- 角色名是否一致。
- 专有名词是否翻译得当。
- merged 片段是否自然。
- model-text-fill 是否瞎补。
- low confidence 行是否应该保留。

这两种完整不能混为一谈。

文档、封面和发布说明里必须说清楚 beta / workflow proof，就是因为 Phase C 更接近“结构完整”，不等于“人工精校完整”。

### 3.4 模型批处理是一门工程，不是把所有行丢给模型

`phase_c_llm_screening_pack_v5/manifest.json` 显示，模型请求被拆成几类：

- `first_pass_match_fix_rows`: `592`
- `remaining_match_fix_rows`: `401`
- `unmatched_rich_rows`: `3446`
- `unmatched_rest_rows`: `67`

并且 batch size 是 `150`。

这说明当问题规模超过几千行时，不能把所有内容塞进一个 prompt。

必须做队列：

1. 哪些是已有匹配但可能错。
2. 哪些是剩余匹配修复。
3. 哪些是 unmatched 但上下文丰富。
4. 哪些是 unmatched 且价值低。
5. 每批最多多少行。
6. 每批用什么 prompt。
7. 每批结果如何 ingest。
8. 哪些没返回。
9. 哪些无法解析。

这就是模型工程和普通聊天的区别。

### 3.5 request profile 说明了吞吐与质量的权衡

`phase_c_model_request_profiles_v1` 里有多个 profile：

- `mixedfast_7500`
- `mixedfast_aggressive_10000`
- `mixedfast_coarse_14000`
- `mixedfast_ultracoarse_22000`
- `mixedfast_hypercoarse_32000`
- `mixedfast_megacoarse_52000`

例如小 profile：

```json
{
  "rows_per_request": 14,
  "max_request_char_budget": 7000,
  "preview_char_limit": 100,
  "context_char_limit": 80
}
```

大 profile：

```json
{
  "rows_per_request": 64,
  "max_request_char_budget": 32000,
  "preview_char_limit": 35,
  "context_char_limit": 25
}
```

这背后是一个典型权衡：

- 每批行数少：上下文更充分，质量更好，但成本高、轮次多。
- 每批行数多：吞吐更高，但上下文变短，模型更容易粗糙处理。

项目后期选择 aggressive / coarse profile，很可能是为了把剩余几千行快速推完。

这适合 beta / workflow proof，但不适合宣称精校。

### 3.6 删除无用中文行是必要质量门

`phase_c_review_report_v5` 里有一个很关键的动作：

- Rows deleted for having no usable Chinese：`3`
- Rows kept after deletion pass：`5153`
- Rows with no usable Chinese remaining under current filter：`0`

这说明系统最后做了一个 gate：

> 如果中文字段完全不可用，就不要为了 coverage 保留它。

这一步很小，但方向正确。

更理想的是把这个 gate 前置，而不是最后才做。

比如可以设计：

- `NO_USABLE_CHINESE`
- `MIXED_LANGUAGE_CONTAMINATION`
- `OCR_NOISE_TOO_HIGH`
- `MODEL_FILL_UNVERIFIED`
- `LOW_CONFIDENCE_KEEP`
- `REQUIRES_HUMAN_REVIEW`

这样输出时就能区分“可发布行”和“只为结构占位的 beta 行”。

## 4. 时间轴和烧录教会的东西

### 4.1 timeaxis 是从数据工程进入视频工程的边界

`phase_c_timeaxis_v36/manifest.json` 显示，它从：

`scratch/phase_c_model_applied_v36/all_segments.json`

导出了四个 part：

- `part01`: `1247`
- `part02`: `1443`
- `part03`: `1353`
- `part04`: `1110`

每个 part 有：

- `zh.srt`
- `bilingual.srt`
- `tsv`

这个目录是一个关键边界：

> 在 timeaxis 之前，问题是数据匹配和文本质量；在 timeaxis 之后，问题是字幕格式、时间轴和视频烧录。

如果 timeaxis 输入有错，烧录只会把错固定进视频。

### 4.2 烧录脚本本身很简单，但它让错误变得昂贵

`scratch/run_hardsub_v36.ps1` 的核心是：

```powershell
ffmpeg -i video -vf subtitles=partXX.zh.srt -c:v h264_nvenc -cq 19 -c:a copy output.mp4
```

字幕样式：

```text
FontName=Microsoft YaHei
FontSize=10
Alignment=2
MarginV=48
Outline=2
Shadow=0
```

这说明最终视频生成不是难点。

难点是：

- 烧录很慢。
- 输出巨大。
- 一旦字幕错，返工成本高。
- 一旦字体位置不合适，需要重新跑视频。
- 一旦源视频路径或 SRT 错，结果全废。

所以烧录前必须有 gate：

1. SRT 是否能 parse。
2. 行数是否符合预期。
3. 时间轴是否单调递增。
4. 是否有空字幕。
5. 是否有明显 OCR 噪声。
6. 是否有抽帧 spot check。
7. 是否确认字幕位置。

`subtitle_position_probe_v1` 就是在解决第 7 点。

### 4.3 字幕位置 probe 很值得保留成方法

`subtitle_position_probe_v1` 里有：

- `part01_source_*`
- `part01_default_*`
- `part01_raised_*`
- `part01_candidate_a/b/c/d/e.png`

这说明最终烧录前做过位置比较。

这一步非常值得保留为标准流程。

原因：

- 字幕太低会被播放器 UI 或平台裁切影响。
- 字幕太高会挡住画面。
- 字幕描边太弱会在亮背景上看不清。
- 字幕字号太大影响观感。

视频字幕不是导出 SRT 就结束了。最终观感必须通过抽帧检查。

## 5. 封面目录教会的东西

`bilibili_covers_v1` 已经另写了一篇专门文档。

这里简单总结：

- 封面不是生成式图片。
- 底图来自真实视频抽帧。
- 文字、标签、遮罩、色块是程序化绘制。
- contact sheet 用来横向 review。
- 真实视频帧 + 确定性字体渲染，比直接让 AI 生成带中文的封面更可靠。

这条经验也适用于字幕：

> 让模型负责判断和文案，让程序负责确定性渲染。

## 6. scratch 的真正问题

`scratch` 的问题不是“没有价值”。

真正问题是：

> 它把高价值的审计线索和低价值的重资产混在一起了。

### 6.1 高价值、低体积

应该保留或迁移到文档/manifest 的东西：

- 当前指针文件。
- final manifest。
- release snapshot README。
- review summary。
- timeaxis manifest。
- hardsub command script。
- model request profile。
- final coverage stats。
- deletion log。
- spot check 结论。

这些东西几十 KB 到几 MB，价值很高。

### 6.2 低价值、高体积

可以清理的东西：

- 已上传并确认不用重传的 `.mp4`。
- 中间 `.wav`。
- Whisper chunk JSON。
- benchmark 视频。
- 重复候选截图。
- 多轮 smoke test 输出。
- 过期 request batches。
- 过期 local responses。
- 旧 applied 版本的大型 `all_segments.json` 副本。

这些东西占几十 GB，但长期学习价值很低。

### 6.3 最大改进：scratch 应该分层

以后建议把 scratch 分成：

```text
scratch/
  _current/
  _archive_manifest/
  _heavy/
  _tmp/
  _delete_after_upload/
```

其中：

- `_current`: 当前正式指针和少量入口。
- `_archive_manifest`: 小体积 manifest、README、报告。
- `_heavy`: 视频、音频、大图。
- `_tmp`: 可随时删的临时试验。
- `_delete_after_upload`: 上传后可删的交付视频。

现在所有东西混在同一层，导致每次清理都很难下手。

## 7. 可执行的清理原则

我不建议在没有二次确认的情况下直接清空整个 `scratch`。

原因：

1. 里面确实有可学习的工程轨迹。
2. 里面有一些最终版本指针和 manifest。
3. 里面可能还有重传、对账、回查需要的元数据。
4. 全清是不可逆操作。

但我建议清理重资产。

### 7.1 第一优先级：可删视频

如果你确认 B 站上传成功、无需本地重传，可以删：

```text
scratch/phase_c_hardsub_v36
```

这一个目录约 `52.78 GB`。

### 7.2 第二优先级：可删分段工作视频和音频

如果不再需要重新 OCR / 重新剪辑，可以删：

```text
scratch/ghost-yotei-part01
scratch/ghost-yotei-part02
scratch/ghost-yotei-part03
scratch/ghost-yotei-part04
scratch/yotei
```

这些合计约 `32 GB`。

### 7.3 第三优先级：可删 benchmark 和 probe 图

可以删：

```text
scratch/english_ocr_bench
scratch/english_ocr_part03_sample
scratch/english_ocr_probe
scratch/subtitle_position_probe_v1
scratch/bilibili_covers_v1
```

但 `bilibili_covers_v1` 如果还想保留封面源图，可先复制到别处再删。

### 7.4 第四优先级：旧模型批处理目录

大量目录如：

```text
phase_c_retry_round1_local_responses_v1..v22
phase_c_model_retry_round1_ingest_v1..v22
phase_c_model_retry_round1_merge_v1..v22
phase_c_burnin_prep_v1..v24
phase_c_llm_screening_pack_v1..v13
```

这些主要是过程痕迹。

如果最终 manifest 已经保存，旧过程目录可以清。

不过它们体积不如视频大，清理优先级低。

## 8. 推荐保留清单

如果要保留最小可回溯集，我建议保留或迁移以下内容到 `docs` 或专门 archive：

### 8.1 Phase B

```text
scratch/PHASE_B_CURRENT_OFFICIAL_VERSION.txt
scratch/phase_b_release_v14_round8_frozen/README.md
scratch/phase_b_release_v14_round8_frozen/manifest.json
scratch/phase_b_final_export_v14_round8/README.md
scratch/phase_b_final_export_v14_round8/manifest.json
```

### 8.2 Phase C

```text
scratch/PHASE_C_CURRENT_BEST.txt
scratch/PHASE_C_CURRENT_MODEL_APPLIED.txt
scratch/PHASE_C_CURRENT_MODEL_REQUESTS.txt
scratch/phase_c_model_applied_v36/manifest.json
scratch/phase_c_timeaxis_v36/manifest.json
scratch/phase_c_review_report_v5/review_summary.md
scratch/phase_c_review_report_v5/review_rows.json
scratch/run_hardsub_v36.ps1
```

### 8.3 封面

```text
scratch/bilibili_covers_v1/cover_contact_sheet.png
scratch/bilibili_covers_v1/source_frames/
```

如果封面已经上传/不再需要复用，这些也可以删。

### 8.4 经验文档

长期应该保留的是文档，而不是 scratch 本身：

- Phase B 小范围人工确认经验。
- Phase C English-first skeleton 经验。
- coverage ratio 风险。
- 模型批处理经验。
- timeaxis / hardsub gate。
- 封面生成流程。
- scratch 清理策略。

这篇文档就是把这些内容从 scratch 中抽出来。

## 9. 最重要的工程教训

### 9.1 长任务必须有 current pointer

目录名不能替代状态。

`v36` 看起来比 `v35` 新，但不一定更正确。

必须有：

```text
CURRENT_BEST
CURRENT_OFFICIAL
CURRENT_MODEL_APPLIED
CURRENT_REQUESTS
CURRENT_RELEASE
```

这类指针文件。

### 9.2 每次阶段完成必须 freeze

否则项目会不断漂移。

Phase B 的 frozen release 是好模式。

Phase C 也应该统一出一个最终 `release_vXX_frozen`，里面只放：

- manifest
- checksums
- entry points
- known issues
- not included heavy assets

### 9.3 不要让 coverage 成为唯一目标

coverage 很诱人。

它可测、可优化、可展示。

但它不能证明字幕质量。

更好的指标组合是：

| 指标 | 用途 |
| --- | --- |
| coverage ratio | 结构完整度 |
| matched-high / medium / low | 自动匹配质量分层 |
| model-text-fill count | 模型补写风险 |
| model-text-replace count | 模型改写风险 |
| no usable Chinese count | 基础可用性 |
| mixed-language contamination count | OCR/模型污染 |
| human-confirmed count | 真正可信样本 |
| spot check pass count | 发布前视觉验证 |

### 9.4 模型输出必须可 ingest、可 diff、可 rollback

Phase C 的目录说明已经在做这件事：

- request batches
- responses
- ingest
- merge
- applied
- deletion log
- handoff
- review report

这是一套正确方向。

以后应该进一步要求：

- 每次模型应用必须记录 source version。
- 每次删除必须记录 deletion reason。
- 每次替换必须记录 before / after。
- 每次 merge 必须生成 diff summary。
- 每次 release 必须能回滚到上一个 frozen snapshot。

### 9.5 重资产和元数据必须分离

最不该发生的是：

```text
50GB 视频
1KB manifest
4MB all_segments.json
几百张截图
几十个模型请求目录
```

全部混在一个 `scratch`。

这样会导致：

- 想清理又怕误删。
- 想提交又怕带上视频。
- 想复盘又被目录淹没。
- 想找最终版本找不到。

正确结构应该是：

```text
artifacts/
  manifests/
  reports/
  release_snapshots/

scratch/
  heavy/
  tmp/
```

## 10. 对这个 scratch 的最终判断

我不建议现在直接“全部清空”。

不是因为里面的重资产都值得留，而是因为里面已经能提炼出明确学习价值：

1. Phase B 展示了小范围人工确认闭环。
2. Phase C 展示了全量字幕工作流如何变复杂。
3. coverage 从 `0.3067` 到 `0.8957` 到 `1.0`，非常适合作为 Goodhart 风险案例。
4. `phase_c_review_report_v5` 暴露了 coverage=1.0 之后仍有 mixed-language contamination。
5. `run_hardsub_v36.ps1` 记录了最终烧录参数。
6. `subtitle_position_probe_v1` 证明了发布前视觉 spot check 的必要性。
7. `bilibili_covers_v1` 证明了真实抽帧 + 程序化排版比直接生成带字封面更稳。

所以我做的是“提炼文档”，而不是走“无价值就清空”的分支。

但从磁盘治理角度，下一步可以清理重资产。

## 11. 如果要清理，我建议这样清

先清最大且最可替代的：

```powershell
Remove-Item -LiteralPath "C:\Users\汪家俊\anime\AnimeTranscoder\scratch\phase_c_hardsub_v36" -Recurse -Force
```

这能释放约 `52.78 GB`。

然后视需要清：

```powershell
Remove-Item -LiteralPath "C:\Users\汪家俊\anime\AnimeTranscoder\scratch\ghost-yotei-part01" -Recurse -Force
Remove-Item -LiteralPath "C:\Users\汪家俊\anime\AnimeTranscoder\scratch\ghost-yotei-part02" -Recurse -Force
Remove-Item -LiteralPath "C:\Users\汪家俊\anime\AnimeTranscoder\scratch\ghost-yotei-part03" -Recurse -Force
Remove-Item -LiteralPath "C:\Users\汪家俊\anime\AnimeTranscoder\scratch\ghost-yotei-part04" -Recurse -Force
Remove-Item -LiteralPath "C:\Users\汪家俊\anime\AnimeTranscoder\scratch\yotei" -Recurse -Force
```

这能再释放约 `32 GB`。

最后再清旧试验包。

但我不建议用“一刀切清空 scratch”作为默认操作，除非你确认：

- 不需要本地重传视频。
- 不需要回查字幕生成过程。
- 不需要封面源图。
- 不需要任何模型请求/响应记录。
- 不需要 OCR benchmark 结果。

## 12. 一句话总结

`scratch` 作为长期保存目录是不合格的，但作为工程考古现场很有价值。

它真正应该留下来的不是那些视频，而是这些经验：

- 用 current pointer 对抗版本迷路。
- 用 frozen snapshot 定义正式版本。
- 用 English-first skeleton 固定时间轴。
- 用 human-confirmed gold set 校准自动扩展。
- 用 batch/request/ingest/merge/applied 管住模型输出。
- 用 review report 防止 coverage 自欺。
- 用 timeaxis manifest 连接数据和视频。
- 用 spot check 检查最终视觉结果。
- 用重资产隔离策略防止 scratch 变成不可清理垃圾场。

所以，这个目录值得提炼，不值得原样长期保留。
