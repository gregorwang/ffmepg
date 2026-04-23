# Plan

本计划用于把《Ghost of Yotei》当前的字幕工作重新收束到一条正确链路：先完成 `Phase A` 的高质量中文字幕正式产出，再进入 `Phase B` 的中英双语对齐。执行上以 `GPU OCR` 为第一优先，`Phase B` 只做模型和数据路线预研，不在 `Phase A` 完成前启动正式对齐。

## Scope
- In:
  - 修复 `GameSubtitleOCR` 的 `GPU` 运行环境并验证 `RTX 2060` 可用
  - 用样本重新调参并确定正式全量参数
  - 为 13 个中文视频统一产出 `raw/cleaned` 的 `SRT + JSON`
  - 定义并冻结第一版清洗规则与量化验收标准
  - 并行做 `Phase B` 的语义匹配技术预研，但不执行正式双语对齐
- Out:
  - 在 `Phase A` 结束前正式运行 13 中文切片到 4 英文 part 的语义对齐
  - 在参数未冻结前继续沿用 CPU 结果做后续生产
  - 纯时间轴硬匹配作为最终双语方案

## Frozen Decisions
- 中文正式产出必须用 `GPU` 环境重跑，之前的 `CPU` 结果只作为验证链路的基线，不作为最终交付。
- `Phase A` 完成前，不推进正式双语对齐。
- `Phase B` 最终以英文时间轴为主轴，中文为补充字段。
- `Phase B` 采用“先恢复 13 切片到 4 part 的全局偏移，再做时间窗约束下的语义匹配”的路线。
- 如果中英文存在一对多或多对一，默认英文为主，只保留最优中文匹配；无法可靠匹配时允许留空，不强配。

## Initial Numeric Rules
- OCR 样本正式候选参数：
  - `model_profile`: 先测 `server`，若 `RTX 2060` 显存不足或持续 `OOM`，立刻回退到 `mobile`
  - `fps`: 候选为 `3 / 4 / 6`
- 清洗规则第一版：
  - 相邻字幕合并相似度阈值：`0.78`
  - 最小有效字符数：`2`
  - 最低置信度阈值：`0.60`
- 清洗补充规则第一版：
  - 低于最低置信度且字符数 `<= 4` 的短碎片优先删除
  - 仅含说话人冒号、半句残片、明显桥接重复条目优先删除
  - `raw` 文件永远保留，所有清洗都输出到 `cleaned` 文件，不覆盖原始结果
- `Phase A` 验收标准：
  - 样本抽检 `50` 条
  - 字符级准确率 `>= 90%`

## Action Items
[ ] 先重建 `GameSubtitleOCR` 的 `GPU` 环境，确认 `paddle` 显示 `COMPILED_WITH_CUDA=True` 且 `paddle.device.get_device()` 返回 `gpu:*`，并记录安装版本、驱动、CUDA 变体与验证结果。  
[ ] 先做样本显存验证，把 `server profile` 作为第一优先候选，在 `RTX 2060 6GB` 上记录显存占用、吞吐和是否稳定；如果不稳定或显存不够，立即回退到 `mobile profile`，不硬上。  
[ ] 重新做样本调参，联合评估 `ROI/crop`、`preprocess profile`、`model_profile`、`fps` 四个维度，至少覆盖清晰对白、动作/火光/模糊、字幕切换快这三类片段。  
[ ] 在样本阶段固定一套正式参数，输出样本的 `raw.srt`、`raw.json`、`cleaned.srt`、`cleaned.json`，并按 `50` 条人工抽检计算字符级准确率，未达到 `90%` 不进入全量。  
[ ] 全量重跑 `C:\Users\汪家俊\Downloads` 下 13 个中文切片视频，统一保留原始结果，并追加清洗后的 `SRT + JSON`，目录结构固定到每个视频独立文件夹下。  
[ ] 为 `Phase A` 产出补一份执行记录，至少包含：使用的正式参数、每个视频输出路径、每个视频的 cue 数量、清洗前后数量变化、抽检样本与问题类型。  
[ ] 并行启动 `Phase B` 预研，但只做技术验证，不做正式对齐：先读取 `scratch\ghost-yotei-part01~04` 下的英文时间线 JSON 和切片元数据，确认是否能恢复 13 中文切片到 4 part 的全局偏移。  
[ ] 并行比较 `Phase B` 的语义匹配候选方案，至少给出本地跨语言 embedding 路线与 LLM 复核路线的优劣、成本、速度和抽检方案，并定义 `Phase B` 的人工抽检环节。  
[ ] 进入 `Phase B` 前再次确认数据约束：以英文为主轴输出双语 JSON，时间窗只负责缩小候选，最终配对由语义评分决定，不允许纯时间重合直接定匹配。  

## Progress 2026-04-16
- `GPU` 环境已重建成功：
  - `RTX 2060 6GB`
  - `nvidia-smi` 驱动：`581.83`
  - `paddlepaddle-gpu==3.2.2`
  - `CudaVariant=cu118`
  - 自检结果：`Paddle 3.2.2`、`CUDA=True`、`DEVICE=gpu:0`
- `server profile` 已在样本上完成显存探测：
  - 测试视频：`37336780446-1-192.mp4`
  - 样本裁剪：`128,525,1024,129`
  - 峰值整卡显存约：`1099 MiB`
  - 结论：`server` 在 `2060` 上能跑，不存在当前阶段的显存瓶颈
- 样本调参已切换到字幕密集片段，不再使用“全片均匀抽样”的零检出结果作为依据：
  - 密集样本：`scratch\sample\37336780446-1-192_dense_05m40s_07m40s.mp4`
  - `mobile/server` 在密集片段上的最佳预处理都落在 `raw-color`
- 当前第一版正式候选参数：
  - `device=gpu`
  - `model_profile=mobile`
  - `crop=128,525,1024,129`
  - `profile=raw-color`
  - `fps=4`
  - `min-confidence=0.60`
  - `similarity-threshold=0.78`
  - `max-gap-frames=2`
  - `min-duration=0.8`
- 当前样本对比结论：
  - `mobile` 在该片段上比 `server` 更快，且净结果更干净
  - `fps=6` 相比 `fps=4` 额外带来的主要是碎片和错字，不值得作为第一版正式参数
  - `server + fps=4` 明显更慢，原始 cue 数也更多，当前没有看到足以覆盖成本的精度收益
- 产出能力已补齐：
  - `extract` 现在会自动同时生成 `SRT + JSON`
  - `JSON` 中保留每条 cue 的 `start/end/duration/text/confidence`
  - 样本验证产物：
    - `scratch\sample\gpu_mobile_extract_fps4\raw.srt`
    - `scratch\sample\gpu_mobile_extract_fps4\raw.json`
- `Phase B` 预研已开始但仍处于只读阶段：
  - 英文时间线文件名在 4 个 part 中并不统一，需要做兼容扫描
  - 已确认的英文时间线样例：
    - `ghost-yotei-part01\transcript.tightened.json`
    - `ghost-yotei-part02\transcript.tightened.vad-g3.json`
    - `ghost-yotei-part03\transcript.tightened.whisper-vad.json`
    - `ghost-yotei-part04\transcript.tightened.vad-g3.json`
  - `part01` 和 `part04` 下存在 `selection.json / selection.vad*.json / atproj / filter.txt` 等元数据，后续优先用于恢复 13 切片到 4 part 的全局偏移

## Progress 2026-04-17
- `Phase A` 抽检流程已工具化：
  - `game-subtitle-ocr prepare-audit`
  - `game-subtitle-ocr score-audit`
- 抽检规则已固化到代码：
  - 抽检包允许直接填写 `reference_text / accepted / notes`
  - 计分采用字符级编辑距离，统一复用 `normalize_text` 后再去空格计分
  - `score-audit` 只有在 `50/50` 全部有参考文本且平均字符级准确率 `>= 0.90` 时才判定通过
- 样本视频新的可评分抽检包已生成：
  - `C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea\37336780446-1-192\audit_50\audit_50.review.json`
  - 配套截图：`audit_001.png` 至 `audit_050.png`
- 样本清洗已继续收紧到 `cleaned_v4`：
  - `C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea\37336780446-1-192\cleaned_v4.json`
  - `C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea\37336780446-1-192\cleaned_v4.srt`
  - 当前样本 `cue_count=217`
  - `<0.75` 的残留条目已压到 `0`
  - 新的抽检包：
    - `C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea\37336780446-1-192\audit_50\audit_50_v4.review.json`
    - 配套截图：`audit_001.png` 至 `audit_050.png`
  - 2026-04-17 人工复核结论：
    - `50` 张样本图整体正确率主观判断已超过 `90%`
    - 明显问题仍存在于少数条目，例如：
      - 个别游戏 UI / 交互提示被误当作字幕
      - 个别复杂中文词如“翻滚”在早期版本中有误识别
      - 少量高置信度幻觉条目仍可能残留
    - 但用户已确认 `cleaned_v4` 相比此前版本更好，并接受其作为当前批量正式参数的清洗版本
- `Phase B` 元数据预研已落成结构化摘要：
  - `scratch\phase_b_probe\ghost_yotei_phase_b_metadata_summary.json`
  - 当前已确认：
    - `part01` 的 `selection.json` 与 `transcript.tightened.json` 完全对齐，`2025/2025` 命中
    - `part04` 的 `selection.vad-g3.json` 与 `transcript.tightened.vad-g3.json` 完全对齐，`462/462` 命中
    - `part04.dialogue-cut.vad-g3.filter.txt` 可解析出 `924` 个保留区间，总保留时长约 `13429.5s`
    - `part02` 和 `part03` 目前没有同级 `selection*.json`，后续需要继续从别的元数据或产物恢复偏移
- 当前状态没有变化：
  - 13 个中文视频的正式 GPU 全量重跑仍未启动
  - 原因是 `50` 条样本人工抽检尚未填写参考文本，因此 `>=90%` 的量化验收门槛还没有被满足

## Deliverables
- `Phase A` 正式参数表
- 13 个中文视频的 `raw/cleaned`：
  - `*.srt`
  - `*.json`
- `Phase A` 抽检记录与准确率结论
- `Phase B` 预研报告：
  - 13 切片到 4 part 的偏移恢复方案
  - 语义匹配模型候选
  - 抽检验证方案

## Open Questions
- `Phase A` 的 `JSON` 最终是采用通用 `cue list` 结构，还是直接对齐到项目现有 `TranscriptDocument` 风格；若不阻塞执行，默认先输出通用 `cue list`。  
- `Phase B` 预研时是否优先使用本地 embedding 模型；若无额外指定，默认先做本地模型方案，再评估是否需要 LLM 复核。  
- 13 个中文切片与 4 个英文 part 的切分关系是否完全可由现有 `selection/transcript/artifacts` 恢复；若不能，则需要追加音频或画面指纹方案。  
