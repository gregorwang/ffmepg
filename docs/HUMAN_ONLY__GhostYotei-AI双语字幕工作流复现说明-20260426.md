# Ghost Yotei AI 双语字幕工作流复现说明

## 0. 文档定位

这份文档是给后续操作者、下一轮 AI 会话、或者想复现实验流程的人看的。

它不把这次产物包装成“完整高质量商业字幕项目”。更准确的定位是：

- 这是一个以 `Ghost Yotei` 四段视频为对象的 AI 工作流实验。
- 目标是验证 Codex/本地脚本/ OCR / ffmpeg / 模型校对能不能组合成一条近似自动化的视频字幕处理流水线。
- 最终产物可以上传、可以学习、可以展示工作流，但不能宣称为严格校对过的完整双语字幕版。
- 本项目大量依赖硬字幕 OCR，源视频清晰度、模型大小、显存限制、切分质量都会直接影响结果。

如果要把这份文档喂给新的 AI，请先告诉它：

> 你不是在从零做一个字幕项目，而是在复现一个已经跑通的实验流水线。请先读本文档，按目录指针检查现有产物，再决定是否重跑某一步。

---

## 1. 项目最终产物概览

### 1.1 当前最终硬字幕视频

最终硬字幕输出目录：

`scratch/phase_c_hardsub_v36`

四个成品视频：

- `scratch/phase_c_hardsub_v36/part01/part01.hardsub.mp4`
- `scratch/phase_c_hardsub_v36/part02/part02.hardsub.mp4`
- `scratch/phase_c_hardsub_v36/part03/part03.hardsub.mp4`
- `scratch/phase_c_hardsub_v36/part04/part04.hardsub.mp4`

这些视频已经用 `ffprobe` 核对过时长，和源视频对齐。

### 1.2 当前最终中文字幕时间轴

四个中文字幕时间轴输出目录：

`scratch/phase_c_timeaxis_v36`

每个 part 都有三类文件：

- `*.zh.srt`：中文字幕轨
- `*.bilingual.srt`：英文 + 中文双语轨
- `*.tsv`：中英文本和元数据对照表

入口 manifest：

`scratch/phase_c_timeaxis_v36/manifest.json`

关键数字：

- 总行数：`5153`
- part 数：`4`
- `part01`: `1247`
- `part02`: `1443`
- `part03`: `1353`
- `part04`: `1110`

### 1.3 当前最终匹配数据

当前匹配数据目录：

`scratch/phase_c_model_applied_v36`

核心文件：

- `scratch/phase_c_model_applied_v36/all_segments.json`
- `scratch/phase_c_model_applied_v36/manifest.json`
- `scratch/phase_c_model_applied_v36/deletion_log.json`

关键数字：

- `total_english_cues`: `5153`
- `matched_cues`: `5153`
- `coverage_ratio`: `1.0`
- `deleted_rows`: `3`

注意：这里的 `coverage_ratio = 1.0` 只是表示每一条保留的英文 cue 都有中文文本字段，不等于每一句都经过人类级精校。

### 1.4 当前指针

当前应用版指针：

`scratch/PHASE_C_CURRENT_MODEL_APPLIED.txt`

当前交接版指针：

`scratch/PHASE_C_CURRENT_MODEL_HANDOFF.txt`

当前它们指向：

- `scratch\phase_c_model_applied_v36`
- `scratch\phase_c_model_handoff_v36`

---

## 2. 推荐公开声明

### 2.1 视频标题可选方向

可以从下面选一个或混合调整：

- `Ghost Yotei 英语学习自用双语字幕 | Codex AI 工作流试验 Beta`
- `用 Codex 做游戏视频双语字幕：Ghost Yotei 工作流实验`
- `Ghost Yotei 中英字幕实验版 | AI OCR + Codex 工作流`
- `AI 自动化双语字幕流程测试：Ghost Yotei Part 01`

### 2.2 B 站视频简介建议文本

可以直接使用下面这段：

> 本视频为英语学习自用与 AI 工作流实验内容。视频中的中英字幕基于官方英文硬字幕、官方中文字幕 OCR/文本、脚本处理、Codex 辅助匹配与 ffmpeg 硬字幕烧录生成。AI 主要用于字幕清洗、官方中英字幕匹配、时间轴整理和复核，不是把英文机翻成中文。字幕并非商业级完整校对版本，部分时间轴、OCR 识别、人名、专名、说话人归属和句子匹配仍可能存在错误。  
>
> 本项目主要用于验证“AI + 本地工具链”在视频剪辑、OCR、字幕匹配、翻译校对和硬字幕烧录中的可行性，重点是工作流实验与英语学习，不代表官方发布版本。  
>
> 声明：英文字幕与中文字幕均以官方字幕来源为基础；本项目工作是抽取、清洗、匹配、整理和烧录，属于实验性工作流，不保证逐句和逐秒完全准确。观看时请以原视频画面语境为准。

### 2.3 封面文字建议

封面主标题建议固定：

`Ghost Yotei`

副标题建议：

`Codex 工作流 AI 试验 Beta`

角标或说明文字建议：

- `英语学习自用`
- `官方英文硬字幕 + 官方中文字幕`
- `中英字幕`
- `非完整精校`

这里可以写官方中英字幕来源，但要同时说明 AI 的角色：

`官方英文硬字幕 + 官方中文字幕`

原因是 AI 不是负责把英文机翻成中文，而是负责官方中文和官方英文之间的清洗、匹配、复核、时间轴整理和烧录。

---

## 3. 输入数据结构

### 3.1 四个英文主视频 part

源视频目录：

- `scratch/ghost-yotei-part01`
- `scratch/ghost-yotei-part02`
- `scratch/ghost-yotei-part03`
- `scratch/ghost-yotei-part04`

本轮硬字幕使用的源视频：

- `scratch/ghost-yotei-part01/part01.dialogue-cut.tight-cq30.mp4`
- `scratch/ghost-yotei-part02/part02.dialogue-cut.vad-g3.fixed.mp4`
- `scratch/ghost-yotei-part03/part03.dialogue-cut.whisper-vad.fixed.mp4`
- `scratch/ghost-yotei-part04/part04.dialogue-cut.vad-g3.fixed.mp4`

这些视频本身已经带英文硬字幕。后续中文字幕烧录要避开英文硬字幕位置。

### 3.2 英文 OCR

英文 OCR 根目录：

`scratch/english_ocr_4parts_v1`

项目路线里曾经尝试过 Whisper/VAD 作为英文文本来源，但后续认识到：如果中文来自画面 OCR，而英文来自语音转写，两个数据层级不同，对齐会更难。因此最后改为英文也从硬字幕 OCR 抽取。

### 3.3 中文 OCR

中文 OCR 根目录在历史文档中记录为：

`C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea`

中文 OCR 不是来自同一条完整时间线，而是来自多个中文切片。因此 Phase B 的一个核心任务是先把中文切片挂回四个英文 part，再做 cue 级匹配。

---

## 4. 工作流总览

整条流程可以分成九个阶段：

1. 准备四个英文视频 part。
2. 对英文硬字幕做 OCR，得到英文 cue。
3. 对中文视频或中文片段做 OCR，得到中文 cue。
4. 在 Phase B 中建立中文片段到英文 part 的映射。
5. 在 Phase C 中以英文 cue 为主轴，尝试把中文挂到英文 cue 上。
6. 使用模型/规则/人工指令式校对补齐低置信行。
7. 删除没有可用中文的行，得到 `v36`。
8. 按四个 part 导出 `zh.srt` 和双语对照。
9. 用 ffmpeg 把中文字幕烧到原视频中，并调整位置避免压住英文硬字幕。

这条流程的关键思想是：

> 英文 cue 是骨架，中文只是挂载字段。

一旦这个原则动摇，就会出现中英文互相拖着跑、时间轴漂移、句子串线的问题。

---

## 5. Phase A：OCR 识别阶段

### 5.1 为什么 OCR 是整个项目的地基

这个项目后面所有匹配、校对、导出、烧录都建立在 OCR 文本上。

如果 OCR 本身有问题，例如：

- 人名识别错
- 短句漏掉
- UI 提示混入字幕
- 一行被切成多行
- 多行被粘成一行
- 英文 `you` 被识别成 `vou`
- 中文 `死` 被识别成 `四`

后续模型会非常吃力。模型可以修复“明显语义可判断”的错误，比如把“杀四他”理解成“杀死他”，但无法稳定修复所有时间轴错位和句子串线。

### 5.2 6GB 显存的实际限制

本机显存只有 6GB，意味着很多最大型 OCR / ASR / 视频理解模型无法舒适运行。

这会导致几个现实限制：

- 不能随意上最大模型做高精度识别。
- 必须更多依赖轻量 OCR、规则清洗和局部复核。
- 遇到低清晰度视频时，OCR 错误会显著增加。
- 字幕越小、压缩越重、背景越复杂，识别越不稳定。

这不是单纯“AI 不够强”，而是输入质量、模型容量、算力约束共同决定的结果。

### 5.3 建议的 OCR 改进方向

如果以后重做，优先级如下：

1. 先拿更高清的视频源。
2. 尽可能避免二次压缩后再 OCR。
3. 对字幕区域做裁剪，只喂字幕带给 OCR。
4. 用多帧聚合，而不是单帧识别。
5. 对同一句字幕出现的多帧结果做投票。
6. 将 UI 文本、地点提示、任务提示和对白字幕分层处理。
7. 对人物名、地名、武器名建立词表。

这些比盲目更换一个更大的语言模型更重要。

---

## 6. Phase B：中文片段到英文 part 的映射

### 6.1 真实问题

这个项目不是“同一个视频文件的中英双轨对齐”。实际结构是：

- 英文侧有 `4` 个长 part。
- 中文侧来自多个切片。

所以 Phase B 要先解决：

> 某个中文 OCR 片段属于哪个英文 part，位于大致哪个区间？

这一步如果错了，后面的 cue 匹配会在错误窗口里找中文，结果必然大量错配。

### 6.2 尝试过的路线

历史中尝试过：

- 全局 embedding 匹配
- 语义相似度匹配
- 顺序对齐
- 高置信锚点抽取
- 局部窗口扩展
- cue 级局部对齐
- 1:N / N:1 合并

早期全局语义匹配只能得到局部有效结果，原因是中英文切分粒度不同，单句和多句经常交错。

### 6.3 最后保留下来的工程经验

更稳的路线是：

1. 先收高置信锚点。
2. 用锚点确定局部窗口。
3. 在局部窗口内做更细的 cue 匹配。
4. 允许 1:N 和 N:1。
5. 不要强行全局一对一。

这个思路适用于很多字幕项目。

字幕对齐不是表格 join，它更像是在两条有噪声的时间线上找局部可置信的锚点，再逐步扩展。

---

## 7. Phase C：英文主轴全量挂中文

### 7.1 当前主轴

Phase C 的主轴是英文 cue。

在本项目中总英文 cue 原始数量是 `5158`。经过后续删除不可用中文行，最终保留 `5153` 条。

### 7.2 为什么需要模型校对

自动匹配会产生三类结果：

- 明显正确的高置信匹配
- 明显未匹配
- 分数低但可能可用的灰区

灰区是最难的。它可能是真的错配，也可能只是 OCR 字错导致分数低。例如用户指出的例子：

`我明天杀四他`

这里的 `四` 很可能是 `死` 的 OCR 错字。如果语境清楚，应该理解为“杀死他”，而不是直接判为低质量。

因此后续校对规则从“低分可疑”调整为“OCR-aware”：

- 明显字形错但语义能判断的，优先修正后保留。
- 完全串句的，删除或重配。
- 没有可用中文的，不保留。

### 7.3 本轮最终版本 v36

最终匹配版本：

`scratch/phase_c_model_applied_v36`

关键结果：

- `total_english_cues`: `5153`
- `matched_cues`: `5153`
- `deleted_rows`: `3`

删除的三条是中文本身已经碎掉，无法当字幕使用的行。

注意：`matched_cues = 5153` 不代表字幕质量完美。它只表示保留下来的每一条英文 cue 都有了中文文本字段。

---

## 8. 时间轴导出

### 8.1 导出目录

`scratch/phase_c_timeaxis_v36`

### 8.2 文件结构

每个 part 包含：

- `partXX.zh.srt`
- `partXX.bilingual.srt`
- `partXX.tsv`

例如：

- `scratch/phase_c_timeaxis_v36/part01/part01.zh.srt`
- `scratch/phase_c_timeaxis_v36/part01/part01.bilingual.srt`
- `scratch/phase_c_timeaxis_v36/part01/part01.tsv`

### 8.3 导出逻辑

导出时按字段：

- `part_name`
- `start`
- `end`
- `english_text`
- `chinese_text`

将 `chinese_text` 写入中文 SRT。

双语版则写：

1. 英文原文
2. 中文文本

### 8.4 风险

如果前面的 cue 匹配错了，导出的 SRT 只会忠实复现错误。导出不是校对步骤，只是格式转换步骤。

---

## 9. 硬字幕烧录

### 9.1 烧录脚本

最终脚本：

`scratch/run_hardsub_v36.ps1`

### 9.2 ffmpeg 核心参数

使用 `subtitles` 过滤器烧录字幕：

```powershell
subtitles='scratch/phase_c_timeaxis_v36/part01/part01.zh.srt':force_style='FontName=Microsoft YaHei,FontSize=10,Alignment=2,MarginV=48,Outline=2,Shadow=0'
```

视频编码：

```powershell
-c:v h264_nvenc
-preset p5
-cq 19
-rc vbr_hq
-b:v 0
-c:a copy
-movflags +faststart
```

### 9.3 字幕位置

原视频已经有英文硬字幕。中文字幕不能使用默认底部位置，否则会压住英文。

最终确认样式：

- `FontName=Microsoft YaHei`
- `FontSize=10`
- `Alignment=2`
- `MarginV=48`
- `Outline=2`
- `Shadow=0`

这个位置位于英文硬字幕上方，距离较近，但不重叠。

### 9.4 检查帧

抽帧检查目录：

`scratch/phase_c_hardsub_v36_spotcheck`

检查图：

- `part01_0310500.png`
- `part02_0122500.png`
- `part03_0053500.png`
- `part04_0009500.png`

检查结果：

- 中文字幕位置一致。
- 没有覆盖原生英文硬字幕。
- 字号可读。
- 在不同亮度场景下黑边足够。

---

## 10. 如何从当前状态重新跑硬字幕

如果已经有 `phase_c_timeaxis_v36`，只想重新烧录：

```powershell
powershell -ExecutionPolicy Bypass -File scratch\run_hardsub_v36.ps1
```

如果要检查 ffmpeg 是否还在跑：

```powershell
Get-Process ffmpeg -ErrorAction SilentlyContinue
```

如果要核对输出文件：

```powershell
Get-ChildItem scratch\phase_c_hardsub_v36 -Recurse -Filter *.mp4 |
  Select-Object FullName,Length,LastWriteTime
```

如果要核对时长：

```powershell
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 <video>
```

---

## 11. 如何抽帧检查

示例：

```powershell
ffmpeg -y -ss 00:03:10.500 `
  -i scratch\phase_c_hardsub_v36\part01\part01.hardsub.mp4 `
  -frames:v 1 -update 1 `
  scratch\phase_c_hardsub_v36_spotcheck\part01_0310500.png
```

抽帧时尽量选：

- 有英文硬字幕的帧
- 有中文字幕的帧
- 明亮场景一张
- 暗场景一张
- 有 UI 的场景一张
- 多行字幕场景一张

只抽没有字幕的风景帧不能证明烧录位置正确。

---

## 12. 质量声明

本项目当前最诚实的质量描述是：

- 视频处理链路已经跑通。
- 四个 part 已经输出硬字幕成品。
- 字幕位置已经通过抽帧检查。
- 中英字幕文本仍有明显错误风险。
- 部分时间轴和句子匹配不可靠。
- 项目更适合作为 AI 工作流实验与英语学习自用，不适合作为公开承诺准确性的字幕版本。

如果要继续提高质量，下一步不应该先改 ffmpeg，而应该回到 OCR 和匹配源头。

---

## 13. 下一轮改进建议

### 13.1 输入源

优先获取更高清的视频源。

低清晰度 + 压缩 + 小字号硬字幕会把 OCR 上限压得很低。

### 13.2 OCR

建议做字幕区域裁剪、多帧投票、词表纠错。

### 13.3 匹配

建议不要追求一次性全自动满覆盖，而是分层：

1. 高置信直接收。
2. 中置信进模型。
3. 低置信保留为空。
4. 不要用覆盖率掩盖质量问题。

### 13.4 模型使用

模型适合：

- 判断明显 OCR 错字。
- 修复短句翻译。
- 解释上下文。
- 生成候选字幕。

模型不适合单独承担：

- 全局时间轴重建。
- 大规模无锚点对齐。
- 没有清晰输入的准确校对。

---

## 14. 给下一轮 AI 的最短指令

如果要把项目交给另一个 AI，可以这样说：

> 你在 `C:\Users\汪家俊\anime\AnimeTranscoder` 工作。当前最终字幕匹配版本是 `scratch/phase_c_model_applied_v36`，最终时间轴是 `scratch/phase_c_timeaxis_v36`，最终硬字幕视频是 `scratch/phase_c_hardsub_v36`。请先读 `docs/HUMAN_ONLY__GhostYotei-AI双语字幕工作流复现说明-20260426.md`，不要从零重跑。若要继续提高质量，优先回到 OCR 和 cue 匹配，不要只改 SRT 格式。

---

## 15. B 站发布材料

### 15.1 封面文件

封面按 B 站常用 16:10 比例输出，尺寸为 `1920x1200`。为了避免 AI 图片模型生成错误中文，封面采用“视频实帧 + 本地字体文字层”的方式生成。

输出目录：

```text
scratch/bilibili_covers_v1/
```

可用封面：

- `scratch/bilibili_covers_v1/ghost_yotei_part01_cover.png`
- `scratch/bilibili_covers_v1/ghost_yotei_part02_cover.png`
- `scratch/bilibili_covers_v1/ghost_yotei_part03_cover.png`
- `scratch/bilibili_covers_v1/ghost_yotei_part04_cover.png`
- `scratch/bilibili_covers_v1/ghost_yotei_workflow_beta_cover.png`

封面生成脚本：

```text
tools/build_bilibili_covers.py
```

当前封面文字基调：

- `Ghost Yotei`
- `Codex 工作流 AI 试验 Beta`
- `英语学习自用`
- `官方英文硬字幕`
- `官方中文字幕`
- `非完整精校`
- `字幕时间轴可能存在误差`

这里的“官方中文字幕”指项目使用的官方中文来源；AI 的作用是清洗、匹配、复核和时间轴整理，不是把英文机翻成中文。

### 15.2 视频简介声明

可直接放到 B 站简介：

```text
本视频为英语学习自用与 AI 工作流实验内容。视频中的中英字幕基于官方英文硬字幕、官方中文字幕 OCR/文本、脚本处理、Codex 辅助匹配与 ffmpeg 硬字幕烧录生成。AI 主要用于字幕清洗、官方中英字幕匹配、时间轴整理和复核，不是把英文机翻成中文。字幕并非商业级完整校对版本，部分时间轴、OCR 识别、人名、专名、说话人归属和句子匹配仍可能存在错误。

本项目主要用于验证“AI + 本地工具链”在视频剪辑、OCR、字幕匹配、翻译校对和硬字幕烧录中的可行性，重点是工作流实验与英语学习，不代表官方发布版本。

声明：英文字幕与中文字幕均以官方字幕来源为基础；本项目工作是抽取、清洗、匹配、整理和烧录，属于实验性工作流，不保证逐句和逐秒完全准确。观看时请以原视频画面语境为准。
```

### 15.3 标题模板

可以按 part 发布：

```text
Ghost Yotei Part 01｜Codex 工作流 AI 试验 Beta｜英语学习自用｜中英字幕
Ghost Yotei Part 02｜Codex 工作流 AI 试验 Beta｜英语学习自用｜中英字幕
Ghost Yotei Part 03｜Codex 工作流 AI 试验 Beta｜英语学习自用｜中英字幕
Ghost Yotei Part 04｜Codex 工作流 AI 试验 Beta｜英语学习自用｜中英字幕
```

如果想更明确质量边界，可以在简介里写，不建议塞进标题里。标题太长会影响点击和阅读。
