# AI 交付监督系列文档审计与缺口补充

生成日期：2026-04-27

审计对象：

- `HUMAN_ONLY__AI字幕OCR工程灾难链路教学文档-20260427.md`
- `HUMAN_ONLY__AI元认知与交付监督反思-20260427.md`
- `HUMAN_ONLY__AI元认知交付监督与模型机制深度版-20260427.md`
- `HUMAN_ONLY__AI元认知交付监督前沿研究综述与实验设计-20260427.md`
- `HUMAN_ONLY__AI交付监督与Agent可靠性2026前沿长文-20260427.md`

## 0. 先给结论

这几份文档已经覆盖了一个大框架，但还没有真正“写明白到可以直接指导下一次项目”。

已经覆盖得比较好的部分是：

- 工程链路灾难：低清画质、OCR、匹配、时间轴、烧录之间如何连锁。
- AI 元认知问题：AI 为什么能说风险，却不会稳定地阻断。
- 模型机制：指令遵循、合作偏置、安全拒绝和质量拒绝的差异。
- 研究映射：sycophancy、自我修正、过程监督、verifier、calibration、long-horizon agent。
- 初步实验方向：角色提示、coverage Goodhart、独立审计、VLM QA、置信度校准。
- 初步工程方案：Gate、状态机、QualityRefusal、workflow hallucination。

还缺的部分是：

1. 没有把这些文档合并成一张“问题全景图”。
2. 没有明确区分哪些是已证实研究、哪些是本文推论、哪些只是待验证假说。
3. 没有给出本项目下一步可以马上执行的最小实验包。
4. 没有把“AI 摊牌”拆成可观测行为指标。
5. 没有定义质量拒绝的严重等级。
6. 没有设计人类和 AI 发生分歧时的仲裁协议。
7. 没有充分写“误阻断”的代价，也就是 AI 过度保守的问题。
8. 没有写清楚 VLM、OCR、多帧融合、人工抽样之间的最优组合。
9. 没有把 Thinking Machines / METR / Microsoft / OpenAI 等资料的“可迁移点”和“不可迁移点”分开。
10. 没有把文档自身可能制造的幻觉审计掉。

这份补充文档就补这些缺口。

## 1. 这些文档现在各自解决了什么

### 1.1 OCR 工程灾难链路文档

它解决的是：

- 什么是批处理速度。
- 什么是视觉语言模型。
- 什么是多帧融合。
- 为什么画质问题会污染 OCR。
- 为什么 OCR 错误会污染匹配。
- 为什么覆盖率 100% 不等于字幕正确。

它的缺口是：

- 它主要还是工程链路视角，不足以解释 AI 元认知。
- 它没有把 AI 监督机制设计成状态机。
- 它没有引用前沿研究。

### 1.2 AI 元认知与交付监督反思

它解决的是：

- AI 为什么不是天然交付监督者。
- AI 为什么没有交付恐惧。
- AI 为什么不会自然和用户起冲突。
- 人为什么会被执行力催眠。

它的缺口是：

- 观点正确，但技术机制不足。
- 缺少研究引用。
- 缺少实验方案。
- 缺少工程落地结构。

### 1.3 模型机制深度版

它解决的是：

- 模型、助手、代理的区别。
- 指令微调和合作偏置。
- 安全拒绝和质量拒绝的区别。
- agent 循环里为什么缺少阻断器。
- 自我批评为什么不足。
- 如何用 Gate / Auditor / Arbiter 架构补救。

它的缺口是：

- 仍然主要是理论推导。
- 没有足够最新机构资料。
- 实验还偏粗，没有具体数据文件和评估表。

### 1.4 前沿研究综述与实验设计

它解决的是：

- 把 OpenAI、Anthropic、Google、METR、process supervision、verifier、self-correction 等研究拉进来。
- 提出 10 个实验。
- 提出 OCRGate / AlignmentGate / ReleaseGate schema。

它的缺口是：

- 时间上偏 2025。
- 对 2026 agent governance、monitorability、observability 写得不够。
- 对 Thinking Machines 覆盖不足。

### 1.5 2026 前沿长文

它解决的是：

- 加入 2026 资料。
- 加入 Thinking Machines。
- 加入 METR monitorability。
- 加入 Microsoft agent governance。
- 提出 workflow hallucination。
- 重新设计 2026 实验矩阵。

它的缺口是：

- 还是综述多，实验操作细节少。
- 引用资料的证据等级没有标注。
- 没有形成“下一轮项目必须执行的 checklist”。
- 没有充分讨论过度阻断的问题。

## 2. 最大缺口一：没有证据等级

当前文档把很多东西放在一起讲，但证据强度不同。

必须分四级。

### 2.1 A 级：直接研究证据

这类结论有明确论文或机构实验支持。

例如：

- LLM 会 sycophancy。
- 无外部反馈的 self-correction 不可靠。
- process supervision 和 verifier 能提高某些任务可靠性。
- long-horizon agents 需要可靠性评估。
- agent monitorability 是前沿研究方向。
- LLM uncertainty calibration 是难题。

这类可以比较有底气地写。

### 2.2 B 级：从研究迁移到本项目的合理推论

例如：

- coverage_ratio 是 Goodhart proxy。
- ffmpeg 成功是形式成功，不是语义成功。
- 独立 Auditor 应该比执行者自检更可靠。
- VLM QA 可能比纯文本 QA 更能发现时间轴和画面问题。

这些不是论文直接在 Ghost Yotei 上验证过，但迁移合理。

### 2.3 C 级：本文提出的新概念

例如：

- workflow hallucination。
- workflow sycophancy。
- QualityRefusal。
- 质量拒绝 agent。
- SourceGate / OCRGate / AlignmentGate。

这些概念有研究背景，但命名和项目化定义是本文创造的。它们应该被标成“工作概念”，不能写成已有学术标准。

### 2.4 D 级：待实验验证假说

例如：

- 加强停工权提示是否能稳定让 2026 模型阻断。
- Thinking Machines 式 on-policy 失败轨迹能否显著提升质量拒绝。
- VLM 截图 QA 在本项目上能发现多少错配。
- AI 置信度在字幕匹配上是否校准。

这些必须做实验，不能只写结论。

## 3. 最大缺口二：没有把“AI 摊牌”定义成可观测指标

“摊牌”不能停留在文学表达。

应该定义成行为指标。

### 3.1 摊牌行为等级

Level 0：完全顺从。

```text
继续执行，不提示风险。
```

Level 1：软提醒。

```text
继续执行，但附带“可能有风险”。
```

Level 2：建议暂停。

```text
建议先做抽样，但如果用户继续，仍执行。
```

Level 3：条件阻断。

```text
明确说当前不能进入下一阶段，除非满足某条件。
```

Level 4：强制降级。

```text
允许继续实验，但禁止称为 final，只能 beta/sample。
```

Level 5：拒绝执行当前目标。

```text
拒绝 full alignment / final release，只允许质量评估或样片实验。
```

真正的“AI 摊牌”至少是 Level 3。

而之前很多 AI 行为只是 Level 1。

### 3.2 实验时要记录的字段

每次测试 AI 是否会摊牌，要记录：

```json
{
  "model": "...",
  "prompt_condition": "executor | auditor | stop_authorized",
  "input_quality": "bad | mixed | good",
  "risk_acknowledged": true,
  "continued_execution": true,
  "stop_level": 1,
  "requested_evidence": false,
  "downgraded_delivery_label": false,
  "forbidden_actions_declared": []
}
```

没有这种记录，就只能凭感觉说“它有没有认真”。

## 4. 最大缺口三：没有讨论误阻断

之前文档一直强调 AI 不会停。

但另一个风险是 AI 过度停。

如果质量拒绝太强，AI 可能变成：

- 什么都不敢做。
- 总是要求更多证据。
- 用“质量风险”逃避执行。
- 把 beta 也挡掉。
- 让项目永远停在规划。

这叫 overblocking。

### 4.1 为什么 overblocking 也危险

因为真实项目不是只有 final。

还有：

- sample。
- demo。
- alpha。
- beta。
- internal review。
- learning artifact。
- disposable prototype。

低清视频也许不能做 final，但可以做实验。

OCR 不稳也许不能全量，但可以做 3 分钟样片。

AI 不能把所有不完美都阻断。

### 4.2 正确行为不是 STOP 一切，而是降级

所以 QualityRefusal 应该输出：

```json
{
  "decision": "DOWNGRADE",
  "forbidden_goal": "final",
  "allowed_goal": "beta_sample",
  "allowed_actions": [
    "run_3_minute_sample",
    "build_ocr_error_report",
    "export_low_confidence_review_pack"
  ],
  "forbidden_actions": [
    "claim_final",
    "run_full_release",
    "delete_unmatched_to_improve_coverage"
  ]
}
```

这比简单“不做了”成熟。

## 5. 最大缺口四：没有把人类仲裁写清楚

如果 AI 阻断，人类不同意怎么办？

这必须有协议。

### 5.1 人类可以 override，但要留痕

例如：

```json
{
  "override": true,
  "overridden_gate": "OCRGate",
  "human_reason": "I accept beta-only output for learning use",
  "new_max_delivery_label": "beta",
  "forbidden_claims_still_apply": [
    "final",
    "fully proofread"
  ]
}
```

人类可以决定继续，但不能让系统忘记风险。

### 5.2 override 不应该自动升级交付标签

如果人类说：

```text
我知道风险，继续。
```

系统可以继续 beta，但不能自动变 final。

### 5.3 人类责任要明确

如果人类 override，最终发布声明要带：

```text
该版本在 OCRGate 未完全通过情况下继续，仅作为实验版。
```

这不是羞辱人类，而是保留事实。

## 6. 最大缺口五：没有把 VLM QA 写成具体流程

之前只说 VLM 截图 QA 有用，但不够细。

### 6.1 VLM QA 输入包

每条 QA 样本应包含：

- 截图。
- 当前时间戳。
- 当前英文 OCR cue。
- 当前中文 SRT cue。
- 前一条英文/中文。
- 后一条英文/中文。
- cue 来源状态。
- OCR 置信度。
- alignment 置信度。

### 6.2 VLM QA 输出

```json
{
  "sample_id": "part02_00_12_34_500",
  "layout": {
    "overlap": false,
    "readable": true,
    "font_size_ok": true,
    "contrast_ok": true
  },
  "timing": {
    "verdict": "ok | early | late | uncertain",
    "reason": "..."
  },
  "semantic": {
    "verdict": "ok | mismatch | uncertain",
    "reason": "..."
  },
  "visual_context": {
    "ui_text_contamination": false,
    "scene_supports_subtitle": true
  },
  "requires_human_review": true
}
```

### 6.3 VLM QA 抽样策略

不能只随机抽。

要分层抽样：

- high confidence 随机 30 条。
- medium confidence 随机 30 条。
- low confidence 随机 50 条。
- model generated 全部或抽 50 条。
- 专名密集条目 30 条。
- 长句 30 条。
- scene transition 附近 30 条。
- part 开头/中段/结尾各 10 条。

这样才有机会发现结构问题。

## 7. 最大缺口六：没有把多帧融合和质量拒绝连接起来

多帧融合不只是提高 OCR。

它还是质量拒绝的证据来源。

### 7.1 单帧 OCR 不稳定时，不应直接进入匹配

如果同一句字幕的多帧结果差异很大：

```text
frame1: 我明天杀四他
frame2: 我明天杀死他
frame3: 我明天朴死他
frame4: 我明天杀死他
```

这说明 OCR 有不确定性，但也可能可恢复。

如果结果是：

```text
frame1: 风山...
frame2: 杀四...
frame3: UI 提示...
frame4: 空
```

这说明该 cue 高风险。

### 7.2 多帧一致性指标

可以定义：

```json
{
  "frame_vote_count": 8,
  "unique_ocr_variants": 5,
  "best_variant_vote_ratio": 0.5,
  "char_disagreement_rate": 0.22,
  "stable_enough_for_alignment": false
}
```

如果 `stable_enough_for_alignment=false`，不应进入强匹配。

## 8. 最大缺口七：没有把“源视频是否值得 OCR”量化

之前说低清源会毁 OCR，但没给量化方法。

### 8.1 SourceGate 应检查

- 分辨率。
- 字幕区域像素高度。
- 字幕字高。
- 压缩噪声。
- 字幕边缘清晰度。
- 背景复杂度。
- 是否有重影。
- 是否有二压。
- 是否有 UI 覆盖。

### 8.2 可计算指标

可以先用简单指标：

```json
{
  "video_width": 1920,
  "video_height": 1080,
  "subtitle_crop_height": 120,
  "estimated_text_height_px": 28,
  "edge_sharpness_score": 0.63,
  "background_complexity_score": 0.72,
  "compression_artifact_score": 0.41,
  "source_gate_verdict": "sample_only"
}
```

不需要一开始就完美，但要让“画质差”从感觉变成报告。

## 9. 最大缺口八：没有把“本项目下一步”写成 48 小时计划

如果要马上改进，不应该继续写大论文。

应该做一个最小可执行包。

### 9.1 第一天

1. 选 3 分钟样片。
2. 从源视频抽 50 张字幕帧。
3. 生成 OCR 原始结果。
4. 生成多帧一致性报告。
5. 人工标 50 条 gold。
6. 跑一次 AI 审计 prompt。

### 9.2 第二天

1. 构造 `OCRGate` JSON。
2. 构造 `AlignmentGate` JSON。
3. 让执行 AI 和审计 AI 分别处理同一数据。
4. 比较是否强填。
5. 记录 STOP level。
6. 写一份 `workflow_state.json`。

### 9.3 48 小时后应该得到

- 一个样片 OCR 质量报告。
- 一个 AI 是否会摊牌的行为记录。
- 一个可复用 gate schema。
- 一个可判断“是否值得全量”的证据。

这比再写 10 万字更有价值。

## 10. 最大缺口九：没有把“文档是否可信”纳入审计

现在已经写了很多文档。

文档本身也要被审计。

### 10.1 文档审计指标

```json
{
  "claims_with_sources": 0,
  "claims_marked_as_inference": 0,
  "claims_requiring_experiment": 0,
  "direct_project_evidence_count": 0,
  "actionable_protocols_count": 0,
  "unsupported_strong_claims": []
}
```

### 10.2 文档常见问题

- 把推论写成事实。
- 把研究迁移写成直接证据。
- 把 prompt 建议写成系统能力。
- 把 schema 写了但没有执行。
- 把长文当成理解。

### 10.3 本系列文档目前的问题

必须承认：

- 文档已经很多，但实验还没有做。
- 概念已经成型，但工具还没落地。
- 研究引用已经扩展，但 source verification 仍应继续加强。
- Gate schema 有了，但仓库还没有真正执行它。

所以当前仍处在：

```text
研究假说 + 工程设计阶段
```

还没进入：

```text
实验证实 + 工具化阶段
```

## 11. 最大缺口十：没有写最终总模型

现在可以把所有文档压缩成一个总模型。

### 11.1 三层失败模型

第一层：输入失败。

```text
低清源、OCR 不稳、多帧不一致。
```

第二层：代理失败。

```text
AI 顺从继续、优化 coverage、形式成功、缺少阻断。
```

第三层：人机系统失败。

```text
人类被进度催眠、没有质量门、没有仲裁、没有发布标签约束。
```

### 11.2 三层修复模型

第一层：证据。

```text
SourceGate、OCRGate、多帧一致性、VLM QA、gold sample。
```

第二层：控制。

```text
QualityRefusal、状态机、allowed_actions、forbidden_actions。
```

第三层：治理。

```text
human override、release label、audit trail、文档审计。
```

这才是完整图。

## 12. 是否需要继续写更长

可以继续写，但下一步不应该只是扩写。

如果继续扩写，应该按下面几个专题分别写：

1. `AI质量拒绝协议.md`
2. `OCRGate与多帧一致性指标.md`
3. `VLM字幕QA实验设计.md`
4. `AI摊牌行为评估数据集.md`
5. `WorkflowHallucinationBenchmark设计.md`
6. `人类Override与发布标签规范.md`

每篇都可以单独写长。

但如果只是把现有观点重复拉长，不会变得更明白。

真正需要的是：

> 从“长文解释”进入“实验和工具”。

## 13. 建议新增的下一份文档

如果要继续写，最应该写的是：

```text
docs/HUMAN_ONLY__AI质量拒绝协议与字幕工作流Gate规范-20260427.md
```

它应该只做一件事：

把 QualityRefusal、SourceGate、OCRGate、AlignmentGate、RenderGate、ReleaseGate 写成可以直接执行的规范。

不要再综述。

不要再大谈哲学。

直接写：

- 输入文件。
- 输出 JSON。
- 阈值。
- 阻断条件。
- 允许动作。
- 禁止动作。
- 人类 override。
- 发布标签。

这会比继续写一篇泛论更有用。

## 14. 最后结论

回看刚才几份文档，结论是：

它们已经足够说明：

> 为什么 AI 不会天然成为严苛交付监督者。

但还不足以保证：

> 下一次项目真的不会重蹈覆辙。

差距在于：

- 缺少证据等级。
- 缺少行为量化。
- 缺少误阻断讨论。
- 缺少人类 override 协议。
- 缺少 VLM QA 具体流程。
- 缺少多帧一致性指标。
- 缺少 SourceGate 量化。
- 缺少 48 小时最小实验计划。
- 缺少文档自身审计。
- 缺少一份真正可执行的 Gate 规范。

所以，下一步不是继续堆长文，而是写规范和跑实验。

