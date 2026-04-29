from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


_GAMEPLAY_PROMPT_RE = re.compile(r"(查看|按住|跳跃|冲刺|翻滚|招架|攻击|防御)")
_LEADING_SPEAKER_RE = re.compile(r"^[^：:\s]{1,10}[：:]\s*")
_EN_SPEAKER_RE = re.compile(r"[A-Z][A-Za-z' .-]{0,30}:\s")
_EN_LEADING_SPEAKER_RE = re.compile(r"^[A-Z][A-Za-z' .-]{0,30}:\s*")
_EN_SPEAKER_CAPTURE_RE = re.compile(r"([A-Z][A-Za-z' .-]{0,30}):")
_EN_ALL_CAPS_RE = re.compile(r"^[A-Z0-9 '&:,.!?-]+$")
_EN_UI_PREFIX_RE = re.compile(r"^(?:[A-Z][A-Z0-9]+(?: [A-Z0-9]+){0,3})\s+(?=[A-Z][A-Za-z' .-]{0,30}:)")
_PAREN_ONLY_RE = re.compile(r"^[\(\[（【].*[\)\]】）]$")
_ZH_SFX_RE = re.compile(r"(尖叫|低哼|喘气|呼吸起伏|哼声|笑|呻吟|痛苦|惊呼|怒吼|哭喊|惨叫)")
_EN_SFX_RE = re.compile(r"\b(screaming|grunt|grunts|panting|chuckles|laughs?|groans?|gasps?|shouts?|cries?|fearful|pained)\b", re.IGNORECASE)
_ZH_LOCATION_PREFIX_RE = re.compile(r"^(?:[一-龥]{2,8}(?:谷|城|寨|河|瀑布|客栈|巢穴|神社))\s*")
_SPEAKER_MAP = {
    "atsu": "笃",
    "jubei": "十兵卫",
    "yone": "米",
    "kengo": "谦吾",
    "oyuki": "阿雪",
    "kiku": "菊",
    "mad goro": "疯五郎",
    "goro": "五郎",
    "commander wada": "和田",
    "wada": "和田",
    "nine tail": "九尾",
    "the snake": "蝮蛇",
    "the kitsune": "狡狐",
    "the spider": "蜘蛛",
    "the dragon": "蛟龙",
    "master enomoto": "榎本",
    "sensei takahashi": "高桥",
    "hanbei": "半兵卫",
    "hana": "花",
}


@dataclass(slots=True)
class ChineseCue:
    clip_name: str
    cue_index: int
    order_index: int
    start: float
    end: float
    text: str
    semantic_text: str
    confidence: float


@dataclass(slots=True)
class EnglishCue:
    segment_id: str
    segment_ids: list[str]
    index: int
    start: float
    end: float
    text: str
    semantic_text: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Sequence-only bilingual alignment using English OCR as primary axis.")
    parser.add_argument("--mapping-json", type=Path, required=True)
    parser.add_argument("--chinese-ocr-root", type=Path, required=True)
    parser.add_argument("--english-ocr-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--model-name", type=str, default="paraphrase-multilingual-MiniLM-L12-v2")
    parser.add_argument("--context-window", type=int, default=2)
    parser.add_argument("--match-threshold", type=float, default=0.46)
    parser.add_argument("--output-threshold", type=float, default=0.5)
    parser.add_argument("--skip-english-penalty", type=float, default=0.015)
    parser.add_argument("--skip-chinese-penalty", type=float, default=0.01)
    parser.add_argument("--band-width-ratio", type=float, default=0.22)
    parser.add_argument("--band-width-min", type=int, default=180)
    parser.add_argument("--progress-weight", type=float, default=0.18)
    parser.add_argument("--min-chinese-confidence", type=float, default=0.88)
    parser.add_argument("--min-output-score", type=float, default=0.62)
    args = parser.parse_args()

    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    model = SentenceTransformer(args.model_name)

    parts_output: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    clips_by_part: dict[str, list[dict[str, Any]]] = {}
    for item in mapping.get("clips") or []:
        clips_by_part.setdefault(str(item["assigned_part"]), []).append(item)

    for part_info in mapping.get("parts") or []:
        part_name = str(part_info["part_name"])
        short_name = part_name.replace("ghost-yotei-", "")
        english_path = args.english_ocr_root / short_name / "cleaned.json"
        english_units = load_english_units(english_path)
        aligned_segments, part_summary = align_part(
            model=model,
            part_name=part_name,
            english_units=english_units,
            clip_assignments=sorted(clips_by_part.get(part_name, []), key=lambda item: int(item.get("clip_order_in_part") or 0)),
            chinese_root=args.chinese_ocr_root,
            context_window=args.context_window,
            match_threshold=args.match_threshold,
            output_threshold=args.output_threshold,
            skip_english_penalty=args.skip_english_penalty,
            skip_chinese_penalty=args.skip_chinese_penalty,
            band_width_ratio=args.band_width_ratio,
            band_width_min=args.band_width_min,
            progress_weight=args.progress_weight,
            min_chinese_confidence=args.min_chinese_confidence,
            min_output_score=args.min_output_score,
        )
        parts_output.append({"part_name": part_name, "segment_count": len(aligned_segments), "segments": aligned_segments})
        summary.append(part_summary)
        print(
            json.dumps(
                {
                    "part_name": part_name,
                    "segment_count": len(aligned_segments),
                    "matched_segment_count": part_summary["matched_segment_count"],
                    "mean_match_score": part_summary["mean_match_score"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    payload = {
        "version": "0.3-sequence",
        "alignment_strategy": "english-ocr-primary + sequential-semantic-alignment",
        "parts": parts_output,
        "summary": summary,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_chinese_sequence(chinese_root: Path, ordered_clip_names: list[str]) -> list[ChineseCue]:
    cues: list[ChineseCue] = []
    order_index = 0
    for clip_name in ordered_clip_names:
        cleaned_path = chinese_root / clip_name / "cleaned.json"
        payload = json.loads(cleaned_path.read_text(encoding="utf-8-sig"))
        for item in payload.get("cues") or []:
            text = str(item.get("text") or "").strip()
            semantic_text = prepare_chinese_text(text)
            if not semantic_text:
                continue
            cues.append(
                ChineseCue(
                    clip_name=clip_name,
                    cue_index=int(item.get("index") or 0),
                    order_index=order_index,
                    start=float(item.get("start") or 0.0),
                    end=float(item.get("end") or 0.0),
                    text=text,
                    semantic_text=semantic_text,
                    confidence=float(item.get("confidence") or 0.0),
                )
            )
            order_index += 1
    return cues


def load_chinese_clip(chinese_root: Path, clip_name: str) -> list[ChineseCue]:
    return load_chinese_sequence(chinese_root, [clip_name])


def load_english_units(english_cleaned_path: Path) -> list[EnglishCue]:
    payload = json.loads(english_cleaned_path.read_text(encoding="utf-8-sig"))
    raw: list[dict[str, Any]] = []
    for index, item in enumerate(payload.get("cues") or [], start=1):
        text = str(item.get("text") or "").strip()
        semantic_text = prepare_english_text(text)
        if not semantic_text:
            continue
        raw.append(
            {
                "segment_id": str(item.get("id") or f"cue_{index:05d}"),
                "start": float(item.get("start") or 0.0),
                "end": float(item.get("end") or 0.0),
                "text": text,
                "semantic_text": semantic_text,
            }
        )

    units: list[EnglishCue] = []
    current: dict[str, Any] | None = None
    for item in raw:
        if current is None:
            current = {
                "segment_ids": [item["segment_id"]],
                "start": item["start"],
                "end": item["end"],
                "texts": [item["semantic_text"]],
                "raw_texts": [item["text"]],
            }
            continue

        can_merge = (
            (float(item["start"]) - float(current["end"]) <= 0.85)
            and ((float(item["end"]) - float(current["start"])) <= 8.0)
            and (sum(len(text) for text in current["texts"]) + len(str(item["semantic_text"])) <= 220)
        )
        if can_merge:
            current["segment_ids"].append(item["segment_id"])
            current["end"] = item["end"]
            current["texts"].append(item["semantic_text"])
            current["raw_texts"].append(item["text"])
            continue

        units.append(finalize_english_unit(len(units), current))
        current = {
            "segment_ids": [item["segment_id"]],
            "start": item["start"],
            "end": item["end"],
            "texts": [item["semantic_text"]],
            "raw_texts": [item["text"]],
        }

    if current is not None:
        units.append(finalize_english_unit(len(units), current))
    return units


def finalize_english_unit(index: int, current: dict[str, Any]) -> EnglishCue:
    segment_ids = [str(item) for item in current["segment_ids"]]
    segment_id = segment_ids[0] if len(segment_ids) == 1 else f"blk_{index + 1:04d}"
    text = " ".join(str(text) for text in current["raw_texts"] if text).strip()
    semantic_text = " ".join(str(text) for text in current["texts"] if text).strip()
    return EnglishCue(
        segment_id=segment_id,
        segment_ids=segment_ids,
        index=index,
        start=float(current["start"]),
        end=float(current["end"]),
        text=text,
        semantic_text=semantic_text,
    )


def align_part(
    model: SentenceTransformer,
    part_name: str,
    english_units: list[EnglishCue],
    clip_assignments: list[dict[str, Any]],
    chinese_root: Path,
    context_window: int,
    match_threshold: float,
    output_threshold: float,
    skip_english_penalty: float,
    skip_chinese_penalty: float,
    band_width_ratio: float,
    band_width_min: int,
    progress_weight: float,
    min_chinese_confidence: float,
    min_output_score: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    outputs = [
        {
            "id": unit.segment_id,
            "segment_ids": unit.segment_ids,
            "start": round(unit.start, 3),
            "end": round(unit.end, 3),
            "english_text": unit.text,
            "chinese_text": "",
            "match_score": None,
            "source_clip": None,
            "source_cue_index": None,
        }
        for unit in english_units
    ]
    if not english_units or not clip_assignments:
        return outputs, {"part_name": part_name, "segment_count": len(outputs), "matched_segment_count": 0, "mean_match_score": None}
    scored: list[float] = []
    total_matches = 0
    total_chinese_cues = 0
    english_midpoints = [((unit.start + unit.end) / 2.0) for unit in english_units]
    english_cursor = 0
    for assignment in clip_assignments:
        clip_name = str(assignment["clip_name"])
        chinese_cues = load_chinese_clip(chinese_root, clip_name)
        chinese_cues = [cue for cue in chinese_cues if cue.confidence >= min_chinese_confidence]
        total_chinese_cues += len(chinese_cues)
        if not chinese_cues:
            continue

        clip_start = float(assignment.get("part_cut_start") or 0.0)
        clip_end = float(assignment.get("part_cut_end") or clip_start)
        search_start, search_end = derive_clip_search_window(assignment, clip_start, clip_end)
        english_indices = [
            index
            for index, midpoint in enumerate(english_midpoints)
            if index >= english_cursor and midpoint >= search_start and midpoint <= search_end
        ]
        if not english_indices:
            continue

        english_slice = [english_units[index] for index in english_indices]
        english_contexts = build_context_texts([unit.semantic_text for unit in english_slice], context_window, 220)
        chinese_contexts = build_context_texts([cue.semantic_text for cue in chinese_cues], max(1, context_window // 2), 180)

        english_base = model.encode([unit.semantic_text for unit in english_slice], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False, batch_size=256)
        english_ctx = model.encode(english_contexts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False, batch_size=256)
        chinese_base = model.encode([cue.semantic_text for cue in chinese_cues], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False, batch_size=256)
        chinese_ctx = model.encode(chinese_contexts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False, batch_size=256)

        similarity = (0.35 * np.matmul(english_base, chinese_base.T)) + (0.65 * np.matmul(english_ctx, chinese_ctx.T))
        similarity += progress_weight * build_progress_matrix(english_slice, chinese_cues, search_start, search_end)
        matches = monotonic_align(
            similarity=similarity,
            match_threshold=match_threshold,
            output_threshold=output_threshold,
            skip_english_penalty=skip_english_penalty,
            skip_chinese_penalty=skip_chinese_penalty,
            band_width=max(min(band_width_min, len(chinese_cues)), int(len(chinese_cues) * band_width_ratio)),
        )

        for english_index, chinese_index, score in matches:
            if score < min_output_score:
                continue
            global_index = english_indices[english_index]
            cue = chinese_cues[chinese_index]
            if not speaker_compatible(english_slice[english_index].text, cue.text):
                continue
            outputs[global_index]["chinese_text"] = cue.text
            outputs[global_index]["match_score"] = round(score, 4)
            outputs[global_index]["source_clip"] = cue.clip_name
            outputs[global_index]["source_cue_index"] = cue.cue_index
            scored.append(score)
            total_matches += 1
        accepted_indices = [english_indices[english_index] for english_index, _, score in matches if score >= min_output_score]
        if accepted_indices:
            english_cursor = max(english_cursor, max(accepted_indices) + 1)

    summary = {
        "part_name": part_name,
        "segment_count": len(outputs),
        "mapped_cue_count": total_chinese_cues,
        "matched_segment_count": total_matches,
        "mean_match_score": round(float(sum(scored) / len(scored)), 4) if scored else None,
    }
    return outputs, summary


def monotonic_align(
    similarity: np.ndarray,
    match_threshold: float,
    output_threshold: float,
    skip_english_penalty: float,
    skip_chinese_penalty: float,
    band_width: int,
) -> list[tuple[int, int, float]]:
    n_eng, n_zh = similarity.shape
    dp = np.full((n_eng + 1, n_zh + 1), -1e9, dtype=np.float32)
    back = np.zeros((n_eng + 1, n_zh + 1), dtype=np.int8)
    dp[0, 0] = 0.0

    for i in range(1, n_eng + 1):
        dp[i, 0] = dp[i - 1, 0] - skip_english_penalty
        back[i, 0] = 1
    for j in range(1, n_zh + 1):
        dp[0, j] = dp[0, j - 1] - skip_chinese_penalty
        back[0, j] = 2

    ratio = (n_zh / max(n_eng, 1))
    for i in range(1, n_eng + 1):
        expected = int((i - 1) * ratio)
        left = max(1, expected - band_width)
        right = min(n_zh, expected + band_width)
        for j in range(left, right + 1):
            score = float(similarity[i - 1, j - 1]) - match_threshold
            best = dp[i - 1, j] - skip_english_penalty
            move = 1
            if dp[i, j - 1] - skip_chinese_penalty > best:
                best = dp[i, j - 1] - skip_chinese_penalty
                move = 2
            diagonal = dp[i - 1, j - 1] + score
            if diagonal > best:
                best = diagonal
                move = 3
            dp[i, j] = best
            back[i, j] = move

    matches: list[tuple[int, int, float]] = []
    i = n_eng
    j = n_zh
    while i > 0 or j > 0:
        move = int(back[i, j])
        if move == 3 and i > 0 and j > 0:
            score = float(similarity[i - 1, j - 1])
            if score >= output_threshold:
                matches.append((i - 1, j - 1, score))
            i -= 1
            j -= 1
        elif move == 2 and j > 0:
            j -= 1
        elif i > 0:
            i -= 1
        else:
            break
    matches.reverse()
    return matches


def build_progress_matrix(
    english_units: list[EnglishCue],
    chinese_cues: list[ChineseCue],
    clip_start: float,
    clip_end: float,
) -> np.ndarray:
    eng_denom = max(clip_end - clip_start, 1e-6)
    zh_denom = max(max(cue.end for cue in chinese_cues), 1e-6)
    eng_progress = np.array([(((unit.start + unit.end) / 2.0) - clip_start) / eng_denom for unit in english_units], dtype=np.float32)
    zh_progress = np.array([(((cue.start + cue.end) / 2.0) / zh_denom) for cue in chinese_cues], dtype=np.float32)
    delta = np.abs(eng_progress[:, None] - zh_progress[None, :])
    return np.clip(1.0 - (delta / 0.35), 0.0, 1.0)


def derive_clip_search_window(assignment: dict[str, Any], fallback_start: float, fallback_end: float) -> tuple[float, float]:
    clip_span = max(fallback_end - fallback_start, 1.0)
    default_start = max(0.0, fallback_start - min(420.0, max(120.0, clip_span * 0.18)))
    default_end = fallback_end + max(1200.0, clip_span * 0.45)

    assigned_part = str(assignment.get("assigned_part") or "")
    semantic_candidates = assignment.get("semantic_candidates") or []
    candidate = next((item for item in semantic_candidates if str(item.get("part_name")) == assigned_part), None)
    if not candidate:
        return default_start, default_end

    chunk_matches = candidate.get("chunk_matches") or []
    if not chunk_matches:
        return default_start, default_end

    centers = [((float(item["window_start_time"]) + float(item["window_end_time"])) * 0.5) for item in chunk_matches]
    median_center = statistics.median(centers)
    max_delta = max(900.0, clip_span * 0.65)
    kept = [
        item
        for item in chunk_matches
        if abs((((float(item["window_start_time"]) + float(item["window_end_time"])) * 0.5) - median_center)) <= max_delta
    ]
    if not kept:
        kept = chunk_matches

    search_start = min(float(item["window_start_time"]) for item in kept) - max(240.0, clip_span * 0.22)
    search_end = max(float(item["window_end_time"]) for item in kept) + max(900.0, clip_span * 0.55)
    return max(0.0, search_start), max(search_start + 1.0, search_end)


def speaker_compatible(english_text: str, chinese_text: str) -> bool:
    chinese_speaker = extract_chinese_speaker(chinese_text)
    if not chinese_speaker:
        return True
    english_speakers = extract_english_speakers(english_text)
    if not english_speakers:
        return True
    return any(
        chinese_speaker == speaker or chinese_speaker.startswith(speaker) or speaker.startswith(chinese_speaker)
        for speaker in english_speakers
    )


def extract_chinese_speaker(text: str) -> str | None:
    normalized = normalize_text(text)
    match = re.match(r"^([^：:\s]{1,12})[：:]\s*", normalized)
    if not match:
        return None
    speaker = match.group(1).strip()
    if not speaker:
        return None
    return speaker


def extract_english_speakers(text: str) -> set[str]:
    speakers: set[str] = set()
    for raw in _EN_SPEAKER_CAPTURE_RE.findall(normalize_text(text)):
        normalized = raw.strip().lower()
        mapped = map_english_speaker(normalized)
        if mapped:
            speakers.add(mapped)
    return speakers


def map_english_speaker(value: str) -> str | None:
    compact = re.sub(r"\s+", " ", value).strip().lower()
    if compact in _SPEAKER_MAP:
        return _SPEAKER_MAP[compact]
    for key, mapped in _SPEAKER_MAP.items():
        if compact.startswith(key):
            return mapped
    return None


def prepare_chinese_text(text: str) -> str:
    normalized = normalize_text(text)
    normalized = _ZH_LOCATION_PREFIX_RE.sub("", normalized)
    normalized = _LEADING_SPEAKER_RE.sub("", normalized)
    normalized = normalized.replace("·", "").replace("...", " ").strip("，。！？：: ")
    if not normalized:
        return ""
    if _PAREN_ONLY_RE.fullmatch(normalized) and _ZH_SFX_RE.search(normalized):
        return ""
    if _ZH_SFX_RE.search(normalized) and len(normalized) <= 8:
        return ""
    if _GAMEPLAY_PROMPT_RE.search(normalized) and len(normalized) <= 8:
        return ""
    return normalized


def prepare_english_text(text: str) -> str:
    normalized = normalize_text(text).replace("[speech]", "").strip()
    normalized = _EN_UI_PREFIX_RE.sub("", normalized)
    normalized = _EN_LEADING_SPEAKER_RE.sub("", normalized)
    speaker_match = _EN_SPEAKER_RE.search(normalized)
    if speaker_match and speaker_match.start() > 0:
        prefix = normalized[: speaker_match.start()].strip(" -|")
        if prefix and (prefix.upper() == prefix or "task" in prefix.lower() or "collect" in prefix.lower()):
            normalized = normalized[speaker_match.start() :].strip()
    normalized = _EN_UI_PREFIX_RE.sub("", normalized)
    normalized = _EN_LEADING_SPEAKER_RE.sub("", normalized).strip()
    if _PAREN_ONLY_RE.fullmatch(normalized) and _EN_SFX_RE.search(normalized):
        return ""
    if _EN_SFX_RE.search(normalized) and len(normalized.split()) <= 3:
        return ""
    word_count = len([word for word in normalized.split(" ") if word])
    if ":" not in normalized and word_count <= 6 and normalized.upper() == normalized and _EN_ALL_CAPS_RE.fullmatch(normalized):
        return ""
    return normalized


def build_context_texts(items: list[str], radius: int, max_chars: int) -> list[str]:
    outputs: list[str] = []
    for index in range(len(items)):
        start = max(0, index - radius)
        end = min(len(items), index + radius + 1)
        merged = " ".join(text for text in items[start:end] if text)
        outputs.append(merged[:max_chars] if merged else items[index])
    return outputs


def normalize_text(text: str) -> str:
    normalized = text.replace("|", "丨").replace("…", "...")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


if __name__ == "__main__":
    main()
