from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Callable

import numpy as np
from sentence_transformers import SentenceTransformer

from phase_b_sequence_align import (
    ChineseCue,
    EnglishCue,
    extract_english_speakers,
    load_chinese_clip,
    normalize_text,
    prepare_english_text,
    prepare_chinese_text,
    speaker_compatible,
)

_SPEAKER_OCR_MAP = {
    "笠": "笃",
    "築": "笃",
    "筑": "笃",
    "答": "笃",
    "算": "笃",
    "半丘卫": "半兵卫",
    "半丘衛": "半兵卫",
    "干兵卫": "半兵卫",
    "广兵卫": "半兵卫",
    "1兵卫": "半兵卫",
    "十丘卫": "十兵卫",
    "十丘衛": "十兵卫",
    "十岳卫": "十兵卫",
    "一兵卫": "十兵卫",
}

_TEXT_FIXES = {
    "好里。 半兵卫：你左臂很弱": "笃：好重。 半兵卫：你左臂很弱。",
    "半兵卫：那你也用单力": "半兵卫：那你也用单刀。",
    "笃：便能听到母亲的三味线·": "笃：便能听到母亲的三味线。",
    "十兵卫：你说恶鬼知道他脚下藏着一座矿井吗?": "十兵卫：你说恶鬼知道他脚下藏着一座矿井吗？",
    "笃：你是怎么把酒弄上来的?": "笃：你是怎么把酒弄上来的？",
    "十兵卫：进城后有何计划？ 一兵卫": "十兵卫：进城后有何计划？",
    "鬼面队：都让他们干好几天了，": "鬼面队：都让他们干好几天了。",
    "斋藤：这趟冒险真有趣，": "斋藤：这趟冒险真有趣。",
    "十兵卫：留下来吃晚餐吧，": "十兵卫：留下来吃晚餐吧。",
    "半兵卫：无论我去哪，他总能找到我，": "半兵卫：无论我去哪，他总能找到我。",
    "（吃力）你吃太多鲑鱼了。": "笃：（吃力）你吃太多鲑鱼了。",
    "十兵卫：矿工的尸体... 笠·在这有此时日了": "笃：矿工的尸体……在这有些时日了。",
    "十兵卫：我永远记得父亲第一次在矿洞中炼成钢的情景，": "十兵卫：我永远记得父亲第一次在矿洞中炼成钢的情景。",
    "十兵卫：我知道你自视为怨灵，": "十兵卫：我知道你自视为怨灵。",
    "笃：会留下伤疤，": "笃：会留下伤疤。",
    "笃：拆了这里，就能拉你上来": "笃：拆了这里，就能拉你上来。",
    "十兵卫：从这走。": "十兵卫：从这边走。",
    "半兵卫：是砍这个。": "半兵卫：是砍这个。",
}

_MANUAL_ROW_OVERRIDES: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {
    (
        "ghost-yotei-part01",
        ("cue_00341", "cue_00342"),
    ): {
        "chinese_cue_ids": ["64", "65"],
        "chinese_text": "笃：好重。 半兵卫：你左臂很弱。",
    },
    (
        "ghost-yotei-part02",
        ("cue_01138", "cue_01139", "cue_01140", "cue_01141"),
    ): {
        "chinese_cue_ids": ["223", "224", "225"],
        "chinese_text": "疯五郎：但袭击神官便是如此下场。 十兵卫：你算什么神官！ 笃：你算什么神官！",
    },
    (
        "ghost-yotei-part02",
        ("cue_01177", "cue_01178"),
    ): {
        "chinese_cue_ids": ["278", "279"],
        "chinese_text": "十兵卫：这里应该就是矿井。 笃：矿工的尸体……",
    },
    (
        "ghost-yotei-part02",
        ("cue_01183", "cue_01184"),
    ): {
        "chinese_cue_ids": ["284", "286"],
        "chinese_text": "十兵卫：我永远记得父亲第一次在矿洞中炼成钢的情景。 十兵卫：就像变戏法一样。",
    },
    (
        "ghost-yotei-part02",
        ("cue_01191", "cue_01192"),
    ): {
        "chinese_cue_ids": ["298", "299"],
        "chinese_text": "笃：竹子烂了，肯定一踩就折。",
    },
}

_MANUAL_ROW_REPLACEMENTS: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {
    (
        "ghost-yotei-part01",
        ("cue_00355", "cue_00356"),
    ): [
        {
            "english_cue_ids": ["cue_00355", "cue_00356"],
            "chinese_cue_ids": ["86"],
            "english_text": "Hanbei: Left arm only. Hanbei: Let's see what you can do.",
            "chinese_text": "半兵卫：只用左手，让我看看你有多大本事。",
            "alignment_type": "2:1",
            "selection_mode": "manual-replacement",
        }
    ],
    (
        "ghost-yotei-part02",
        ("cue_01081", "cue_01082", "cue_01083"),
    ): [
        {
            "english_cue_ids": ["cue_01081", "cue_01082", "cue_01083"],
            "chinese_cue_ids": ["153"],
            "english_text": "Atsu: He's nowhere to go except off a cliff. Jubei: Somehow, I think he'd still survive. Atsu: Probably.",
            "chinese_text": "笃：他除了跳下悬崖无处可逃。",
            "alignment_type": "3:1",
            "selection_mode": "manual-replacement",
        }
    ],
    (
        "ghost-yotei-part02",
        ("cue_01185", "cue_01186"),
    ): [
        {
            "english_cue_ids": ["cue_01185"],
            "chinese_cue_ids": ["287"],
            "english_text": "Atsu: In another life, I might have followed in his footsteps.",
            "chinese_text": "笃：也许在另一世，我会继承他的衣钵。",
            "alignment_type": "1:1",
            "selection_mode": "manual-replacement",
        }
    ],
    (
        "ghost-yotei-part02",
        ("cue_01138", "cue_01139", "cue_01140", "cue_01141"),
    ): [
        {
            "english_cue_ids": ["cue_01138", "cue_01139", "cue_01140", "cue_01141"],
            "chinese_cue_ids": ["223", "224", "227", "229"],
            "english_text": "Mad Goro: But that's what happens when you attack a priest. Jubei: You're not a priest! Atsu: You're not a priest! Mad Goro: Need more fire? Mad Goro: I'm happy to oblige.",
            "chinese_text": "疯五郎：但袭击神官便是如此下场。 十兵卫：你算什么神官！ 笃：你算什么神官！ 疯五郎：迦具土来也！",
            "alignment_type": "4:4",
            "selection_mode": "manual-replacement",
        }
    ],
    (
        "ghost-yotei-part02",
        ("cue_01208", "cue_01209"),
    ): [
        {
            "english_cue_ids": ["cue_01208", "cue_01209"],
            "chinese_cue_ids": ["323"],
            "english_text": "Jubei: Atsu, Jubei: I know you see yourself as an onry.",
            "chinese_text": "十兵卫：我知道你自视为怨灵。",
            "alignment_type": "2:1",
            "selection_mode": "manual-replacement",
        }
    ],
    (
        "ghost-yotei-part02",
        ("cue_01212", "cue_01213", "cue_01214"),
    ): [
        {
            "english_cue_ids": ["cue_01212", "cue_01213", "cue_01214"],
            "chinese_cue_ids": ["326", "327"],
            "english_text": "Jubei: but what I find most amazing Jubei: is the girl I remember—my sister— Jubei: is still in there.",
            "chinese_text": "十兵卫：但世间好事莫过于，我记忆中的姐姐始终未变。",
            "alignment_type": "3:2",
            "selection_mode": "manual-replacement",
        }
    ]
}


@dataclass(slots=True)
class Group:
    start_pos: int
    end_pos: int
    cue_ids: list[str]
    start: float
    end: float
    text: str
    semantic_text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local cue-level bilingual alignment around validated anchor clusters."
    )
    parser.add_argument(
        "--anchor-json",
        type=Path,
        default=Path("scratch/phase_b_anchor_expansion_v2.json"),
    )
    parser.add_argument(
        "--chinese-ocr-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--english-ocr-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_cue_local_align_v1.json"),
    )
    parser.add_argument(
        "--output-tsv",
        type=Path,
        default=Path("scratch/phase_b_cue_local_align_v1.tsv"),
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="paraphrase-multilingual-mpnet-base-v2",
    )
    parser.add_argument("--parts", nargs="*", default=["ghost-yotei-part01", "ghost-yotei-part02"])
    parser.add_argument("--min-chinese-confidence", type=float, default=0.90)
    parser.add_argument("--flank-seconds", type=float, default=8.0)
    parser.add_argument("--flank-cues", type=int, default=5)
    parser.add_argument("--max-en-group", type=int, default=3)
    parser.add_argument("--max-zh-group", type=int, default=3)
    parser.add_argument("--match-threshold", type=float, default=0.60)
    parser.add_argument("--output-threshold", type=float, default=0.68)
    parser.add_argument("--skip-en-penalty", type=float, default=0.08)
    parser.add_argument("--skip-zh-penalty", type=float, default=0.05)
    return parser.parse_args()


def load_english_raw_cues(english_cleaned_path: Path) -> list[EnglishCue]:
    payload = json.loads(english_cleaned_path.read_text(encoding="utf-8-sig"))
    outputs: list[EnglishCue] = []
    for index, item in enumerate(payload.get("cues") or [], start=1):
        text = str(item.get("text") or "").strip()
        semantic_text = prepare_english_text(text)
        if not semantic_text:
            continue
        cue_id = str(item.get("id") or f"cue_{index:05d}")
        outputs.append(
            EnglishCue(
                segment_id=cue_id,
                segment_ids=[cue_id],
                index=len(outputs),
                start=float(item.get("start") or 0.0),
                end=float(item.get("end") or 0.0),
                text=text,
                semantic_text=semantic_text,
            )
        )
    return outputs


def clean_output_text(text: str) -> str:
    value = normalize_text(str(text))
    value = re.sub(r"^(?:[一-龥]{2,8}(?:谷|城|寨|河|瀑布|客栈|巢穴|神社))\s*", "", value)
    return value.rstrip("@#| ").strip()


def canonicalize_fragment(text: str, expected_speaker: str | None = None) -> str:
    value = clean_output_text(text)
    value = re.sub(r"\s+[一-龥]{1,4}[：:]$", "", value)
    match = re.match(r"^([^：:·•\s]{1,6})[·•:：]\s*(.*)$", value)
    if match:
        raw_speaker = match.group(1).strip()
        rest = match.group(2).strip()
        speaker = _SPEAKER_OCR_MAP.get(raw_speaker, raw_speaker)
        if expected_speaker and speaker != expected_speaker and (raw_speaker in _SPEAKER_OCR_MAP or len(raw_speaker) <= 2):
            speaker = expected_speaker
        return f"{speaker}：{rest}" if rest else f"{speaker}："
    if expected_speaker and re.match(r"^[^：:]{1,2}[·•]", value):
        return re.sub(r"^[^：:]{1,2}[·•]\s*", f"{expected_speaker}：", value)
    value = _TEXT_FIXES.get(value, value)
    return value


def merge_english_fragments(items: list[str]) -> str:
    outputs: list[str] = []
    for raw in items:
        text = clean_output_text(raw)
        if not text:
            continue
        current_cmp = re.sub(r"[\s,.!?;:']", "", text)
        if not current_cmp:
            continue
        if not outputs:
            outputs.append(text)
            continue
        prev = outputs[-1]
        prev_cmp = re.sub(r"[\s,.!?;:']", "", prev)
        if current_cmp == prev_cmp:
            continue
        if current_cmp in prev_cmp:
            continue
        if prev_cmp in current_cmp:
            outputs[-1] = text
            continue
        outputs.append(text)
    return " ".join(outputs)


def merge_output_fragments(items: list[str], expected_speaker: str | None = None) -> str:
    outputs: list[str] = []
    for raw in items:
        text = canonicalize_fragment(raw, expected_speaker=expected_speaker)
        if not text:
            continue
        current_cmp = re.sub(r"[，。！？：:\s·,.!?]", "", text)
        if not current_cmp:
            continue
        if not outputs:
            outputs.append(text)
            continue
        prev = outputs[-1]
        prev_cmp = re.sub(r"[，。！？：:\s·,.!?]", "", prev)
        if current_cmp == prev_cmp:
            continue
        if current_cmp in prev_cmp:
            continue
        if prev_cmp in current_cmp:
            outputs[-1] = text
            continue
        outputs.append(text)
    merged = " ".join(outputs)
    merged = _TEXT_FIXES.get(merged, merged)
    if merged.endswith("?"):
        merged = merged[:-1] + "？"
    if merged.endswith("·"):
        merged = merged[:-1] + "。"
    return merged


def infer_expected_speaker(english_text: str) -> str | None:
    speakers = sorted(extract_english_speakers(english_text))
    if len(speakers) == 1:
        return speakers[0]
    return None


def build_groups_from_english(cues: list[EnglishCue], max_group: int) -> dict[tuple[int, int], Group]:
    groups: dict[tuple[int, int], Group] = {}
    for start in range(len(cues)):
        for size in range(1, max_group + 1):
            end = start + size - 1
            if end >= len(cues):
                break
            chunk = cues[start : end + 1]
            text = " ".join(item.text for item in chunk if item.text).strip()
            semantic_text = " ".join(item.semantic_text for item in chunk if item.semantic_text).strip()
            groups[(start, size)] = Group(
                start_pos=start,
                end_pos=end,
                cue_ids=[item.segment_id for item in chunk],
                start=float(chunk[0].start),
                end=float(chunk[-1].end),
                text=text,
                semantic_text=semantic_text,
            )
    return groups


def build_groups_from_chinese(cues: list[ChineseCue], max_group: int) -> dict[tuple[int, int], Group]:
    groups: dict[tuple[int, int], Group] = {}
    for start in range(len(cues)):
        for size in range(1, max_group + 1):
            end = start + size - 1
            if end >= len(cues):
                break
            chunk = cues[start : end + 1]
            text = " ".join(item.text for item in chunk if item.text).strip()
            semantic_text = " ".join(item.semantic_text for item in chunk if item.semantic_text).strip()
            groups[(start, size)] = Group(
                start_pos=start,
                end_pos=end,
                cue_ids=[str(item.cue_index) for item in chunk],
                start=float(chunk[0].start),
                end=float(chunk[-1].end),
                text=text,
                semantic_text=semantic_text,
            )
    return groups


def embed_texts(
    model: SentenceTransformer,
    texts: list[str],
    embedding_lookup: Callable[[list[str], int], np.ndarray] | None = None,
) -> dict[str, np.ndarray]:
    unique = [text for text in dict.fromkeys(texts) if text]
    if not unique:
        return {}
    if embedding_lookup is not None:
        matrix = embedding_lookup(unique, 128)
    else:
        matrix = model.encode(
            unique,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=128,
        )
    return {text: matrix[index] for index, text in enumerate(unique)}


def score_groups(
    en_group: Group,
    zh_group: Group,
    embed_cache: dict[str, np.ndarray],
    en_window_start: float,
    en_window_end: float,
    zh_window_start: float,
    zh_window_end: float,
) -> float | None:
    if not speaker_compatible(en_group.text, zh_group.text):
        return None
    en_vec = embed_cache.get(en_group.semantic_text)
    zh_vec = embed_cache.get(zh_group.semantic_text)
    if en_vec is None or zh_vec is None:
        return None

    semantic = float(np.dot(en_vec, zh_vec))
    if semantic < 0.50:
        return None

    en_mid = (en_group.start + en_group.end) * 0.5
    zh_mid = (zh_group.start + zh_group.end) * 0.5
    en_progress = (en_mid - en_window_start) / max(en_window_end - en_window_start, 1e-6)
    zh_progress = (zh_mid - zh_window_start) / max(zh_window_end - zh_window_start, 1e-6)
    progress_score = max(0.0, 1.0 - (abs(en_progress - zh_progress) / 0.26))

    en_span = max(en_group.end - en_group.start, 0.25)
    zh_span = max(zh_group.end - zh_group.start, 0.25)
    duration_ratio = min(en_span, zh_span) / max(en_span, zh_span)

    group_penalty = 0.0
    if len(en_group.cue_ids) != len(zh_group.cue_ids):
        group_penalty = 0.02 * abs(len(en_group.cue_ids) - len(zh_group.cue_ids))

    return (0.76 * semantic) + (0.16 * progress_score) + (0.08 * duration_ratio) - group_penalty


def align_window(
    english_cues: list[EnglishCue],
    chinese_cues: list[ChineseCue],
    model: SentenceTransformer,
    max_en_group: int,
    max_zh_group: int,
    match_threshold: float,
    output_threshold: float,
    skip_en_penalty: float,
    skip_zh_penalty: float,
    embedding_lookup: Callable[[list[str], int], np.ndarray] | None = None,
) -> list[dict[str, Any]]:
    if not english_cues or not chinese_cues:
        return []

    en_groups = build_groups_from_english(english_cues, max_en_group)
    zh_groups = build_groups_from_chinese(chinese_cues, max_zh_group)
    embed_cache = embed_texts(
        model,
        [group.semantic_text for group in en_groups.values()] + [group.semantic_text for group in zh_groups.values()],
        embedding_lookup=embedding_lookup,
    )

    n_en = len(english_cues)
    n_zh = len(chinese_cues)
    dp = np.full((n_en + 1, n_zh + 1), -1e9, dtype=np.float32)
    back: dict[tuple[int, int], tuple[str, int, int, float | None]] = {}
    dp[0, 0] = 0.0

    en_window_start = english_cues[0].start
    en_window_end = english_cues[-1].end
    zh_window_start = chinese_cues[0].start
    zh_window_end = chinese_cues[-1].end

    for i in range(n_en + 1):
        for j in range(n_zh + 1):
            current = float(dp[i, j])
            if current <= -1e8:
                continue
            if i < n_en:
                candidate = current - skip_en_penalty
                if candidate > dp[i + 1, j]:
                    dp[i + 1, j] = candidate
                    back[(i + 1, j)] = ("skip_en", 1, 0, None)
            if j < n_zh:
                candidate = current - skip_zh_penalty
                if candidate > dp[i, j + 1]:
                    dp[i, j + 1] = candidate
                    back[(i, j + 1)] = ("skip_zh", 0, 1, None)
            for en_size in range(1, max_en_group + 1):
                if i + en_size > n_en:
                    break
                en_group = en_groups[(i, en_size)]
                for zh_size in range(1, max_zh_group + 1):
                    if j + zh_size > n_zh:
                        break
                    zh_group = zh_groups[(j, zh_size)]
                    score = score_groups(
                        en_group=en_group,
                        zh_group=zh_group,
                        embed_cache=embed_cache,
                        en_window_start=en_window_start,
                        en_window_end=en_window_end,
                        zh_window_start=zh_window_start,
                        zh_window_end=zh_window_end,
                    )
                    if score is None:
                        continue
                    candidate = current + (score - match_threshold)
                    if candidate > dp[i + en_size, j + zh_size]:
                        dp[i + en_size, j + zh_size] = candidate
                        back[(i + en_size, j + zh_size)] = ("match", en_size, zh_size, score)

    outputs: list[dict[str, Any]] = []
    i = n_en
    j = n_zh
    while i > 0 or j > 0:
        move = back.get((i, j))
        if move is None:
            break
        action, en_size, zh_size, score = move
        if action == "match":
            start_i = i - en_size
            start_j = j - zh_size
            en_group = en_groups[(start_i, en_size)]
            zh_group = zh_groups[(start_j, zh_size)]
            if score is not None and score >= output_threshold:
                en_text = merge_output_fragments(
                    [english_cues[pos].text for pos in range(start_i, i)]
                )
                en_text = merge_english_fragments(
                    [english_cues[pos].text for pos in range(start_i, i)]
                )
                expected_speaker = infer_expected_speaker(en_text)
                zh_text = merge_output_fragments(
                    [chinese_cues[pos].text for pos in range(start_j, j)],
                    expected_speaker=expected_speaker,
                )
                outputs.append(
                    {
                        "english_cue_ids": en_group.cue_ids,
                        "chinese_cue_ids": zh_group.cue_ids,
                        "english_text": en_text or en_group.text,
                        "chinese_text": zh_text or clean_output_text(zh_group.text),
                        "match_score": round(float(score), 4),
                        "alignment_type": f"{en_size}:{zh_size}",
                        "start": round(float(en_group.start), 3),
                        "end": round(float(en_group.end), 3),
                    }
                )
            i = start_i
            j = start_j
        elif action == "skip_en":
            i -= 1
        elif action == "skip_zh":
            j -= 1
        else:
            break
    outputs.reverse()
    return outputs


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "\t".join(
            [
                "part_name",
                "cluster_id",
                "alignment_type",
                "match_score",
                "start",
                "end",
                "source_clip",
                "english_cue_ids",
                "chinese_cue_ids",
                "english_text",
                "chinese_text",
            ]
        )
    ]
    for row in rows:
        lines.append(
            "\t".join(
                [
                    str(row.get("part_name", "")),
                    str(row.get("cluster_id", "")),
                    str(row.get("alignment_type", "")),
                    f"{row.get('match_score', 0.0):.4f}",
                    str(row.get("start", "")),
                    str(row.get("end", "")),
                    str(row.get("source_clip", "")),
                    ",".join(row.get("english_cue_ids") or []),
                    ",".join(row.get("chinese_cue_ids") or []),
                    str(row.get("english_text", "")).replace("\t", " ").replace("\n", " "),
                    str(row.get("chinese_text", "")).replace("\t", " ").replace("\n", " "),
                ]
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def gather_cluster_anchor_rows(anchor_doc: dict[str, Any], cluster: dict[str, Any]) -> list[dict[str, Any]]:
    part_name = str(cluster["part_name"])
    source_clip = str(cluster["source_clip"])
    cluster_id = str(cluster["cluster_id"])
    anchor_start = float(cluster["anchor_start"])
    anchor_end = float(cluster["anchor_end"])
    rows: list[dict[str, Any]] = []
    for row in anchor_doc.get("flat_candidates") or []:
        if str(row["part_name"]) != part_name or str(row["source_clip"]) != source_clip:
            continue
        row_cluster_id = str(row.get("cluster_id") or "")
        if row_cluster_id == cluster_id:
            rows.append(row)
            continue
        if str(row.get("selection_mode") or "") == "anchor":
            row_start = float(row.get("start") or 0.0)
            if row_start >= anchor_start - 1.0 and row_start <= anchor_end + 1.0:
                rows.append(row)
    return rows


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    outputs: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (item["part_name"], item["cluster_id"], item["start"])):
        key = (row["part_name"], ",".join(row["english_cue_ids"]))
        if key in seen:
            continue
        seen.add(key)
        outputs.append(row)
    return outputs


def refine_chinese_subset_for_row(
    row: dict[str, Any],
    model: SentenceTransformer,
    chinese_lookup: dict[int, ChineseCue],
) -> dict[str, Any]:
    cue_ids = [int(item) for item in row.get("chinese_cue_ids") or []]
    if len(cue_ids) <= 1:
        row["chinese_text"] = merge_output_fragments(
            [row.get("chinese_text", "")],
            expected_speaker=infer_expected_speaker(str(row.get("english_text") or "")),
        )
        return row

    english_text = str(row.get("english_text") or "").strip()
    english_sem = prepare_english_text(english_text)
    expected_speaker = infer_expected_speaker(english_text)
    multi_speaker = len(extract_english_speakers(english_text)) >= 2
    min_subset_size = 2 if multi_speaker and len(cue_ids) >= 2 else 1
    if not english_sem:
        return row

    best_score = -1e9
    best_subset = cue_ids
    best_text = str(row.get("chinese_text") or "")
    en_vec = model.encode(
        [english_sem],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    for start in range(len(cue_ids)):
        for end in range(start, len(cue_ids)):
            subset = cue_ids[start : end + 1]
            if len(subset) < min_subset_size:
                continue
            cues = [chinese_lookup[item] for item in subset if item in chinese_lookup]
            if not cues:
                continue
            merged = merge_output_fragments([cue.text for cue in cues], expected_speaker=expected_speaker)
            zh_sem = prepare_chinese_text(merged)
            if not zh_sem:
                continue
            zh_vec = model.encode(
                [zh_sem],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )[0]
            semantic = float(np.dot(en_vec, zh_vec))
            zh_span = max(cues[-1].end - cues[0].start, 0.25)
            en_span = max(float(row.get("end") or 0.0) - float(row.get("start") or 0.0), 0.25)
            duration_ratio = min(en_span, zh_span) / max(en_span, zh_span)
            score = (0.88 * semantic) + (0.07 * duration_ratio) - (0.05 * (len(subset) - 1))
            if score > best_score:
                best_score = score
                best_subset = subset
                best_text = merged

    row["chinese_cue_ids"] = [str(item) for item in best_subset]
    row["chinese_text"] = best_text
    row["alignment_type"] = f"{len(row.get('english_cue_ids') or [])}:{len(best_subset)}"
    return row


def add_anchor_fallbacks(
    rows: list[dict[str, Any]],
    cluster_anchor_rows: list[dict[str, Any]],
    english_lookup: dict[str, EnglishCue],
    chinese_lookup: dict[int, ChineseCue],
    cluster_id: str,
    part_name: str,
    source_clip: str,
) -> list[dict[str, Any]]:
    covered_english_ids = {
        cue_id
        for row in rows
        for cue_id in row.get("english_cue_ids") or []
    }
    outputs = list(rows)
    for anchor_row in cluster_anchor_rows:
        if str(anchor_row.get("selection_mode") or "") != "anchor":
            continue
        anchor_ids = [str(item) for item in anchor_row.get("segment_ids") or []]
        if not anchor_ids or any(cue_id in covered_english_ids for cue_id in anchor_ids):
            continue
        english_chunk = [english_lookup[cue_id] for cue_id in anchor_ids if cue_id in english_lookup]
        zh_index = int(anchor_row.get("source_cue_index") or 0)
        zh_cue = chinese_lookup.get(zh_index)
        if not english_chunk or zh_cue is None:
            continue
        outputs.append(
            {
                "english_cue_ids": [cue.segment_id for cue in english_chunk],
                "chinese_cue_ids": [str(zh_cue.cue_index)],
                "english_text": merge_output_fragments([cue.text for cue in english_chunk]),
                "english_text": merge_english_fragments([cue.text for cue in english_chunk]),
                "chinese_text": merge_output_fragments(
                    [zh_cue.text],
                    expected_speaker=infer_expected_speaker(
                        merge_english_fragments([cue.text for cue in english_chunk])
                    ),
                ),
                "match_score": round(float(anchor_row.get("match_score") or 0.0), 4),
                "alignment_type": f"{len(english_chunk)}:1",
                "start": round(float(english_chunk[0].start), 3),
                "end": round(float(english_chunk[-1].end), 3),
                "part_name": part_name,
                "cluster_id": cluster_id,
                "source_clip": source_clip,
                "selection_mode": "anchor-fallback",
            }
        )
        covered_english_ids.update(anchor_ids)
    return outputs


def postprocess_cluster_rows(
    rows: list[dict[str, Any]],
    model: SentenceTransformer,
    chinese_lookup: dict[int, ChineseCue],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for row in rows:
        fixed = dict(row)
        fixed["english_text"] = merge_english_fragments([str(fixed.get("english_text") or "")])
        fixed = refine_chinese_subset_for_row(fixed, model=model, chinese_lookup=chinese_lookup)
        outputs.append(fixed)
    return outputs


def apply_manual_row_overrides(rows: list[dict[str, Any]], part_name: str) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for row in rows:
        fixed = dict(row)
        key = (part_name, tuple(fixed.get("english_cue_ids") or []))
        replacements = _MANUAL_ROW_REPLACEMENTS.get(key)
        if replacements:
            for replacement in replacements:
                clone = dict(fixed)
                clone.update(replacement)
                outputs.append(clone)
            continue
        override = _MANUAL_ROW_OVERRIDES.get(key)
        if override:
            fixed["chinese_cue_ids"] = list(override["chinese_cue_ids"])
            fixed["chinese_text"] = str(override["chinese_text"])
            fixed["alignment_type"] = f"{len(fixed.get('english_cue_ids') or [])}:{len(fixed['chinese_cue_ids'])}"
            fixed["selection_mode"] = "manual-override"
        outputs.append(fixed)
    return outputs


def main() -> None:
    args = parse_args()
    anchor_doc = json.loads(args.anchor_json.read_text(encoding="utf-8"))
    model = SentenceTransformer(args.model_name)

    cluster_rows: list[dict[str, Any]] = []
    cluster_summary_out: list[dict[str, Any]] = []

    for cluster in anchor_doc.get("cluster_summary") or []:
        part_name = str(cluster["part_name"])
        if args.parts and part_name not in set(args.parts):
            continue
        short_name = part_name.replace("ghost-yotei-", "")
        english_path = args.english_ocr_root / short_name / "cleaned.json"
        english_cues_all = load_english_raw_cues(english_path)

        cluster_anchor_rows = gather_cluster_anchor_rows(anchor_doc, cluster)
        if not cluster_anchor_rows:
            continue

        anchor_start = float(cluster["anchor_start"])
        anchor_end = float(cluster["anchor_end"])
        english_cues = [
            cue
            for cue in english_cues_all
            if cue.start >= anchor_start - args.flank_seconds and cue.start <= anchor_end + args.flank_seconds
        ]
        if not english_cues:
            continue

        source_clip = str(cluster["source_clip"])
        chinese_all = [
            cue
            for cue in load_chinese_clip(args.chinese_ocr_root, source_clip)
            if cue.confidence >= args.min_chinese_confidence
        ]
        if not chinese_all:
            continue

        anchor_indices = [int(row["source_cue_index"]) for row in cluster_anchor_rows if row.get("source_cue_index") is not None]
        if not anchor_indices:
            continue
        min_anchor_index = min(anchor_indices) - args.flank_cues
        max_anchor_index = max(anchor_indices) + args.flank_cues
        chinese_cues = [
            cue
            for cue in chinese_all
            if cue.cue_index >= min_anchor_index and cue.cue_index <= max_anchor_index
        ]
        if not chinese_cues:
            continue

        aligned = align_window(
            english_cues=english_cues,
            chinese_cues=chinese_cues,
            model=model,
            max_en_group=args.max_en_group,
            max_zh_group=args.max_zh_group,
            match_threshold=args.match_threshold,
            output_threshold=args.output_threshold,
            skip_en_penalty=args.skip_en_penalty,
            skip_zh_penalty=args.skip_zh_penalty,
        )

        for row in aligned:
            row["part_name"] = part_name
            row["cluster_id"] = str(cluster["cluster_id"])
            row["source_clip"] = source_clip
            row["selection_mode"] = "cue-local"
        aligned = add_anchor_fallbacks(
            rows=aligned,
            cluster_anchor_rows=cluster_anchor_rows,
            english_lookup={cue.segment_id: cue for cue in english_cues},
            chinese_lookup={cue.cue_index: cue for cue in chinese_cues},
            cluster_id=str(cluster["cluster_id"]),
            part_name=part_name,
            source_clip=source_clip,
        )
        aligned = postprocess_cluster_rows(
            rows=aligned,
            model=model,
            chinese_lookup={cue.cue_index: cue for cue in chinese_cues},
        )
        aligned = apply_manual_row_overrides(aligned, part_name=part_name)
        cluster_rows.extend(aligned)
        scores = [row["match_score"] for row in aligned]
        cluster_summary_out.append(
            {
                "cluster_id": str(cluster["cluster_id"]),
                "part_name": part_name,
                "source_clip": source_clip,
                "alignment_count": len(aligned),
                "mean_match_score": round(mean(scores), 4) if scores else None,
                "english_window_start": round(english_cues[0].start, 3),
                "english_window_end": round(english_cues[-1].end, 3),
                "chinese_index_min": chinese_cues[0].cue_index,
                "chinese_index_max": chinese_cues[-1].cue_index,
            }
        )
        print(
            json.dumps(
                {
                    "cluster_id": str(cluster["cluster_id"]),
                    "part_name": part_name,
                    "aligned": len(aligned),
                    "mean_match_score": round(mean(scores), 4) if scores else None,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    flat_rows = dedupe_rows(cluster_rows)
    parts_map: dict[str, list[dict[str, Any]]] = {}
    for row in flat_rows:
        parts_map.setdefault(row["part_name"], []).append(row)
    for rows in parts_map.values():
        rows.sort(key=lambda item: (item["start"], item["end"], ",".join(item["english_cue_ids"])))

    summary: list[dict[str, Any]] = []
    parts_output: list[dict[str, Any]] = []
    for part_name in sorted(parts_map):
        rows = parts_map[part_name]
        scores = [row["match_score"] for row in rows]
        parts_output.append({"part_name": part_name, "segments": rows, "segment_count": len(rows)})
        summary.append(
            {
                "part_name": part_name,
                "segment_count": len(rows),
                "mean_match_score": round(mean(scores), 4) if scores else None,
            }
        )

    payload = {
        "version": "phase-b-cue-local-align-v1",
        "alignment_strategy": "anchor-cluster local cue-level alignment with 1:N / N:1 DP",
        "parts": parts_output,
        "summary": summary,
        "cluster_summary": cluster_summary_out,
        "flat_candidates": flat_rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, flat_rows)
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()
