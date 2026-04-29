from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .models import Rect, SubtitleCue
from .postprocess import cues_to_srt
from .utils import chinese_ratio, ensure_dir, latin_ratio, looks_like_subtitle, normalize_text, save_json, text_similarity


_SRT_TIME_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})",
    re.MULTILINE,
)
_ALL_CAPS_ASCII_RE = re.compile(r"^[A-Z0-9 '&:,.!?-]+$")


def parse_srt(path: Path) -> list[SubtitleCue]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\r?\n\r?\n+", text.strip())
    cues: list[SubtitleCue] = []

    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue

        time_line_index = 1 if lines[0].isdigit() else 0
        if time_line_index >= len(lines):
            continue

        match = _SRT_TIME_RE.search(lines[time_line_index])
        if match is None:
            continue

        text_lines = lines[time_line_index + 1 :]
        if not text_lines:
            continue

        cues.append(
            SubtitleCue(
                index=len(cues) + 1,
                start_seconds=_parse_srt_timestamp(match.group("start")),
                end_seconds=_parse_srt_timestamp(match.group("end")),
                text="\n".join(text_lines).strip(),
                confidence=1.0,
            )
        )

    return cues


def write_cues_json(
    output_path: Path,
    cues: list[SubtitleCue],
    source_path: Path,
    language: str = "zh-Hans",
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = {
        "version": "1.0",
        "source_path": str(source_path),
        "language": language,
        "cue_count": len(cues),
        "metadata": metadata or {},
        "cues": [
            {
                "id": f"cue_{index:05d}",
                "index": index,
                "start": round(cue.start_seconds, 3),
                "end": round(cue.end_seconds, 3),
                "duration": round(max(0.0, cue.end_seconds - cue.start_seconds), 3),
                "text": normalize_text(cue.text),
                "confidence": round(float(cue.confidence), 4),
            }
            for index, cue in enumerate(cues, start=1)
        ],
    }
    save_json(output_path, payload)


def clean_subtitle_cues(
    cues: list[SubtitleCue],
    similarity_threshold: float = 0.72,
    max_merge_gap_seconds: float = 0.6,
    min_text_length: int = 2,
    min_confidence: float | None = None,
    language: str = "ch",
) -> list[SubtitleCue]:
    materialized = [
        SubtitleCue(
            index=cue.index,
            start_seconds=cue.start_seconds,
            end_seconds=max(cue.end_seconds, cue.start_seconds),
            text=normalize_text(cue.text),
            confidence=cue.confidence,
        )
        for cue in cues
        if _should_keep_cue(
            cue.text,
            cue.confidence,
            duration_seconds=max(0.0, cue.end_seconds - cue.start_seconds),
            min_text_length=min_text_length,
            min_confidence=min_confidence,
            language=language,
        )
    ]

    deduplicated: list[SubtitleCue] = []
    for cue in materialized:
        if not deduplicated:
            deduplicated.append(cue)
            continue

        previous = deduplicated[-1]
        if _should_merge_cues(
            previous,
            cue,
            similarity_threshold=similarity_threshold,
            max_merge_gap_seconds=max_merge_gap_seconds,
        ):
            deduplicated[-1] = _merge_two_cues(previous, cue)
            continue

        deduplicated.append(cue)

    bridged = _drop_bridge_cues(deduplicated, similarity_threshold=similarity_threshold)
    clustered = _collapse_dense_overlap_clusters(bridged)
    return _reindex_cues(clustered)


def align_english_transcript_to_chinese(
    english_json_path: Path,
    chinese_cues_path: Path,
    output_path: Path,
    max_offset_seconds: float = 1.5,
) -> None:
    english_payload = json.loads(english_json_path.read_text(encoding="utf-8-sig"))
    english_segments = english_payload.get("Segments") or english_payload.get("segments") or []
    chinese_cues = load_cues_from_path(chinese_cues_path)

    bilingual_segments: list[dict[str, Any]] = []
    chinese_index = 0

    for segment_index, segment in enumerate(english_segments, start=1):
        english_start = float(segment.get("Start") or segment.get("start") or 0.0)
        english_end = float(segment.get("End") or segment.get("end") or english_start)
        english_text = str(segment.get("Text") or segment.get("text") or "").strip()

        while chinese_index < len(chinese_cues) and chinese_cues[chinese_index].end_seconds < english_start - max_offset_seconds:
            chinese_index += 1

        candidates: list[tuple[int, SubtitleCue, float, float]] = []
        scan_index = chinese_index
        while scan_index < len(chinese_cues):
            cue = chinese_cues[scan_index]
            if cue.start_seconds > english_end + max_offset_seconds:
                break

            overlap_seconds = _overlap_seconds(english_start, english_end, cue.start_seconds, cue.end_seconds)
            center_distance = abs(((english_start + english_end) / 2.0) - ((cue.start_seconds + cue.end_seconds) / 2.0))
            if overlap_seconds > 0 or center_distance <= max_offset_seconds:
                candidates.append((scan_index, cue, overlap_seconds, center_distance))
            scan_index += 1

        selected = _select_alignment_candidates(candidates, max_offset_seconds=max_offset_seconds)
        chinese_texts = _dedupe_texts([item[1].text for item in selected])
        match_type = "overlap" if any(item[2] > 0 for item in selected) else ("nearby" if selected else "unmatched")

        bilingual_segments.append(
            {
                "id": str(segment.get("Id") or segment.get("id") or f"bi_{segment_index:05d}"),
                "start": round(english_start, 3),
                "end": round(english_end, 3),
                "duration": round(max(0.0, english_end - english_start), 3),
                "english_text": english_text,
                "chinese_text": " / ".join(chinese_texts),
                "english_segment_id": str(segment.get("Id") or segment.get("id") or ""),
                "chinese_indices": [item[1].index for item in selected],
                "match_type": match_type,
            }
        )

    payload = {
        "version": "1.0",
        "english_source": str(english_json_path),
        "chinese_source": str(chinese_cues_path),
        "segment_count": len(bilingual_segments),
        "max_offset_seconds": max_offset_seconds,
        "segments": bilingual_segments,
    }
    save_json(output_path, payload)


def load_cues_from_path(path: Path) -> list[SubtitleCue]:
    if path.suffix.lower() == ".srt":
        return parse_srt(path)

    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and "cues" in payload:
        return [
            SubtitleCue(
                index=int(item.get("index") or idx),
                start_seconds=float(item.get("start") or item.get("start_seconds") or 0.0),
                end_seconds=float(item.get("end") or item.get("end_seconds") or 0.0),
                text=str(item.get("text") or "").strip(),
                confidence=float(item.get("confidence") or 1.0),
            )
            for idx, item in enumerate(payload["cues"], start=1)
        ]

    raise ValueError(f"Unsupported subtitle cue file: {path}")


def prepare_audit_dataset(
    cues_path: Path,
    output_path: Path,
    sample_count: int = 50,
    source_video_path: Path | None = None,
    crop: Rect | None = None,
    ffmpeg_bin: str | None = None,
) -> dict[str, Any]:
    cues = load_cues_from_path(cues_path)
    if not cues:
        raise ValueError(f"No cues available for audit: {cues_path}")

    sampled = _sample_cues_for_audit(cues, sample_count=sample_count)
    output_dir = ensure_dir(output_path.parent)

    payload: dict[str, Any] = {
        "source_video": str(source_video_path) if source_video_path is not None else None,
        "source_subtitles": str(cues_path),
        "sample_count": len(sampled),
        "crop": crop.to_dict() if crop is not None else None,
        "items": [],
    }

    for audit_index, cue in enumerate(sampled, start=1):
        midpoint = round((cue.start_seconds + cue.end_seconds) / 2.0, 3)
        image_name: str | None = None
        if source_video_path is not None and crop is not None:
            image_name = f"audit_{audit_index:03d}.png"
            _extract_audit_frame(
                source_video_path=source_video_path,
                midpoint_seconds=midpoint,
                crop=crop,
                output_path=output_dir / image_name,
                ffmpeg_bin=ffmpeg_bin,
            )

        payload["items"].append(
            {
                "audit_index": audit_index,
                "cue_id": f"cue_{cue.index:05d}",
                "start": round(cue.start_seconds, 3),
                "end": round(cue.end_seconds, 3),
                "midpoint": midpoint,
                "text": normalize_text(cue.text),
                "confidence": round(float(cue.confidence), 4),
                "image": image_name,
                "reference_text": "",
                "accepted": None,
                "notes": "",
            }
        )

    save_json(output_path, payload)
    return payload


def score_audit_dataset(
    audit_path: Path,
    output_path: Path | None = None,
    pass_threshold: float = 0.9,
) -> dict[str, Any]:
    payload = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    items = payload.get("items") or []

    scored_items: list[dict[str, Any]] = []
    missing_reference_items: list[dict[str, Any]] = []
    accuracies: list[float] = []

    for item in items:
        predicted_text = str(item.get("text") or "")
        reference_text = str(item.get("reference_text") or "")
        accepted = item.get("accepted")

        if not reference_text.strip():
            missing_reference_items.append(
                {
                    "audit_index": int(item.get("audit_index") or 0),
                    "cue_id": str(item.get("cue_id") or ""),
                    "text": normalize_text(predicted_text),
                }
            )
            continue

        character_accuracy = _character_accuracy(predicted_text, reference_text)
        accuracies.append(character_accuracy)
        scored_items.append(
            {
                "audit_index": int(item.get("audit_index") or 0),
                "cue_id": str(item.get("cue_id") or ""),
                "predicted_text": normalize_text(predicted_text),
                "reference_text": normalize_text(reference_text),
                "character_accuracy": round(character_accuracy, 4),
                "exact_match": _normalize_for_character_accuracy(predicted_text)
                == _normalize_for_character_accuracy(reference_text),
                "accepted": accepted,
                "notes": str(item.get("notes") or ""),
            }
        )

    scored_items.sort(key=lambda item: item["character_accuracy"])
    average_accuracy = (sum(accuracies) / len(accuracies)) if accuracies else None

    report = {
        "audit_path": str(audit_path),
        "total_items": len(items),
        "scored_items": len(scored_items),
        "missing_reference_items": len(missing_reference_items),
        "pass_threshold": pass_threshold,
        "average_character_accuracy": round(average_accuracy, 4) if average_accuracy is not None else None,
        "passed": (
            average_accuracy is not None
            and len(scored_items) == len(items)
            and average_accuracy >= pass_threshold
        ),
        "worst_items": scored_items[:10],
        "missing_reference_preview": missing_reference_items[:10],
    }

    if output_path is not None:
        save_json(output_path, report)
    return report


def _parse_srt_timestamp(raw: str) -> float:
    hours, minutes, seconds_millis = raw.split(":")
    seconds, millis = seconds_millis.split(",")
    total_seconds = (int(hours) * 3600) + (int(minutes) * 60) + int(seconds)
    return total_seconds + (int(millis) / 1000.0)


def _should_keep_cue(
    text: str,
    confidence: float,
    duration_seconds: float,
    min_text_length: int,
    min_confidence: float | None,
    language: str,
) -> bool:
    normalized = normalize_text(text)
    stripped = normalized.replace(" ", "")
    language = (language or "ch").lower()
    if len(stripped) < min_text_length:
        return False
    if language == "en":
        lowered = normalized.lower()
        if "mkiceandfire" in lowered:
            return False
        words = [word for word in re.split(r"\s+", normalized) if word]
        if (
            ":" not in normalized
            and len(words) <= 5
            and normalized.upper() == normalized
            and _ALL_CAPS_ASCII_RE.fullmatch(normalized) is not None
        ):
            return False
        if min_confidence is not None and confidence < min_confidence and duration_seconds <= 1.05 and len(stripped) <= 18:
            return False
        if not looks_like_subtitle(normalized, language="en") and latin_ratio(normalized) < 0.35:
            return False
        if len(stripped) <= 2 and not any(char.isalpha() for char in stripped):
            return False
        return True

    if min_confidence is not None and confidence < min_confidence:
        if duration_seconds <= 1.05 and len(stripped) <= 24:
            return False
        if len(stripped) <= 4:
            return False
        if not looks_like_subtitle(normalized, language="ch"):
            return False
        if len(stripped) <= 8 and not any(marker in normalized for marker in ["。", "！", "?", "？", "：", ":"]):
            return False
    if _looks_like_gameplay_prompt(normalized):
        return False
    if not looks_like_subtitle(normalized, language="ch") and chinese_ratio(normalized) < 0.35:
        return False
    if stripped.endswith(("：", ":")) and len(stripped) <= 10:
        return False
    if len(stripped) <= 3 and chinese_ratio(normalized) < 0.8:
        return False
    return True


def _should_merge_cues(
    left: SubtitleCue,
    right: SubtitleCue,
    similarity_threshold: float,
    max_merge_gap_seconds: float,
) -> bool:
    gap = right.start_seconds - left.end_seconds
    if gap > max_merge_gap_seconds:
        return False

    left_norm = normalize_text(left.text)
    right_norm = normalize_text(right.text)
    if left_norm == right_norm:
        return True
    if left_norm in right_norm or right_norm in left_norm:
        longer = left_norm if len(left_norm) >= len(right_norm) else right_norm
        if _looks_like_multi_part_text(longer):
            return False
        return True
    return text_similarity(left_norm, right_norm) >= similarity_threshold


def _merge_two_cues(left: SubtitleCue, right: SubtitleCue) -> SubtitleCue:
    left_quality = _cue_quality(left)
    right_quality = _cue_quality(right)
    selected_text = left.text if left_quality >= right_quality else right.text
    return SubtitleCue(
        index=left.index,
        start_seconds=min(left.start_seconds, right.start_seconds),
        end_seconds=max(left.end_seconds, right.end_seconds),
        text=selected_text,
        confidence=max(left.confidence, right.confidence),
    )


def _cue_quality(cue: SubtitleCue) -> float:
    normalized = normalize_text(cue.text)
    stripped = normalized.replace(" ", "")
    duration = max(0.0, cue.end_seconds - cue.start_seconds)
    score = 0.0
    score += min(1.0, len(stripped) / 16.0)
    score += min(1.0, duration / 2.5)
    language = "en" if latin_ratio(normalized) > chinese_ratio(normalized) else "ch"
    score += latin_ratio(normalized) if language == "en" else chinese_ratio(normalized)
    score += max(0.0, min(1.0, cue.confidence)) * 0.75
    if looks_like_subtitle(normalized, language=language):
        score += 0.8
    if stripped.endswith(("。", "！", "？", ")", "）")):
        score += 0.2
    if (normalized.count("（") == normalized.count("）") and "（" in normalized) or (
        normalized.count("(") == normalized.count(")") and "(" in normalized
    ):
        score += 0.15
    if stripped.endswith(("：", ":", "，", ",", "·")):
        score -= 0.35
    colon_pos = max(normalized.rfind("："), normalized.rfind(":"))
    if colon_pos >= 0 and colon_pos > int(len(normalized) * 0.6):
        score -= 0.4
    return score


def _looks_like_multi_part_text(text: str) -> bool:
    normalized = normalize_text(text)
    speaker_markers = normalized.count("：") + normalized.count(":")
    sentence_breaks = sum(normalized.count(marker) for marker in ["。", "！", "?", "？"])
    return speaker_markers >= 2 or sentence_breaks >= 2


def _looks_like_gameplay_prompt(text: str) -> bool:
    normalized = normalize_text(text).replace(" ", "")
    if normalized in {"跳跃", "查看", "按住", "查看：按住", "查看，按住", "查看:按住", "查看：按住△"}:
        return True
    if normalized.startswith(("查看：", "查看，", "查看:")) and "按住" in normalized:
        return True
    return False


def _contains_substantive(container: str, content: str) -> bool:
    normalized_container = normalize_text(container).replace(" ", "").rstrip("。！？!?，,：:")
    normalized_content = normalize_text(content).replace(" ", "").rstrip("。！？!?，,：:")
    if not normalized_container or not normalized_content:
        return False
    return normalized_content in normalized_container


def _drop_bridge_cues(cues: list[SubtitleCue], similarity_threshold: float) -> list[SubtitleCue]:
    if len(cues) < 3:
        return cues

    filtered: list[SubtitleCue] = [cues[0]]
    for index in range(1, len(cues) - 1):
        previous = filtered[-1]
        current = cues[index]
        following = cues[index + 1]
        if _is_bridge_cue(previous, current, following, similarity_threshold=similarity_threshold):
            continue
        filtered.append(current)
    filtered.append(cues[-1])
    return filtered


def _collapse_dense_overlap_clusters(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    if len(cues) < 4:
        return cues

    collapsed: list[SubtitleCue] = []
    cluster: list[SubtitleCue] = [cues[0]]

    for cue in cues[1:]:
        cluster_end = max(item.end_seconds for item in cluster)
        if cue.start_seconds <= cluster_end + 0.5:
            cluster.append(cue)
            continue
        collapsed.extend(_resolve_dense_cluster(cluster))
        cluster = [cue]

    collapsed.extend(_resolve_dense_cluster(cluster))
    return collapsed


def _resolve_dense_cluster(cluster: list[SubtitleCue]) -> list[SubtitleCue]:
    if len(cluster) < 4:
        return cluster

    cluster_start = min(cue.start_seconds for cue in cluster)
    cluster_end = max(cue.end_seconds for cue in cluster)
    cluster_span = cluster_end - cluster_start
    if cluster_span > 6.0:
        return cluster

    durations = [max(0.0, cue.end_seconds - cue.start_seconds) for cue in cluster]
    short_count = sum(1 for duration in durations if duration <= 1.0)
    average_duration = sum(durations) / len(durations)
    if short_count < max(3, len(cluster) - 1) and average_duration > 1.4:
        return cluster

    best = max(
        cluster,
        key=lambda cue: (_cue_quality(cue), cue.confidence, max(0.0, cue.end_seconds - cue.start_seconds)),
    )
    return [best]


def _is_bridge_cue(
    previous: SubtitleCue,
    current: SubtitleCue,
    following: SubtitleCue,
    similarity_threshold: float,
) -> bool:
    current_duration = max(0.0, current.end_seconds - current.start_seconds)
    if current_duration > 1.2:
        return False

    previous_text = normalize_text(previous.text)
    current_text = normalize_text(current.text)
    following_text = normalize_text(following.text)

    previous_matches = _contains_substantive(current_text, previous_text) or text_similarity(previous_text, current_text) >= similarity_threshold
    following_matches = _contains_substantive(current_text, following_text) or text_similarity(following_text, current_text) >= similarity_threshold

    if not (previous_matches and following_matches):
        return False

    return len(current_text) > max(len(previous_text), len(following_text))


def _reindex_cues(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    return [
        SubtitleCue(
            index=index,
            start_seconds=cue.start_seconds,
            end_seconds=cue.end_seconds,
            text=cue.text,
            confidence=cue.confidence,
        )
        for index, cue in enumerate(cues, start=1)
    ]


def _overlap_seconds(
    left_start: float,
    left_end: float,
    right_start: float,
    right_end: float,
) -> float:
    return max(0.0, min(left_end, right_end) - max(left_start, right_start))


def _select_alignment_candidates(
    candidates: list[tuple[int, SubtitleCue, float, float]],
    max_offset_seconds: float,
) -> list[tuple[int, SubtitleCue, float, float]]:
    if not candidates:
        return []

    overlapping = [item for item in candidates if item[2] > 0]
    if overlapping:
        selected = overlapping
    else:
        best = min(candidates, key=lambda item: item[3])
        selected = [best] if best[3] <= max_offset_seconds else []

    selected.sort(key=lambda item: item[1].start_seconds)
    return selected


def _dedupe_texts(texts: list[str]) -> list[str]:
    deduped: list[str] = []
    for text in texts:
        normalized = normalize_text(text)
        if not normalized:
            continue
        if normalized in deduped:
            continue
        deduped.append(normalized)
    return deduped


def _sample_cues_for_audit(cues: list[SubtitleCue], sample_count: int) -> list[SubtitleCue]:
    if sample_count <= 0:
        raise ValueError("sample_count must be greater than 0")
    if len(cues) <= sample_count:
        return cues
    if sample_count == 1:
        return [cues[len(cues) // 2]]

    selected: list[SubtitleCue] = []
    last_index = -1
    step = (len(cues) - 1) / float(sample_count - 1)
    for slot in range(sample_count):
        cue_index = int(round(slot * step))
        if cue_index <= last_index:
            cue_index = min(len(cues) - 1, last_index + 1)
        selected.append(cues[cue_index])
        last_index = cue_index
    return selected


def _extract_audit_frame(
    source_video_path: Path,
    midpoint_seconds: float,
    crop: Rect,
    output_path: Path,
    ffmpeg_bin: str | None,
) -> None:
    command = [
        ffmpeg_bin or "ffmpeg",
        "-y",
        "-ss",
        f"{midpoint_seconds:.3f}",
        "-i",
        str(source_video_path),
        "-frames:v",
        "1",
        "-vf",
        f"crop={crop.width}:{crop.height}:{crop.x}:{crop.y}",
        str(output_path),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def _character_accuracy(predicted_text: str, reference_text: str) -> float:
    predicted = _normalize_for_character_accuracy(predicted_text)
    reference = _normalize_for_character_accuracy(reference_text)
    if not predicted and not reference:
        return 1.0
    if not predicted or not reference:
        return 0.0

    distance = _levenshtein_distance(predicted, reference)
    return max(0.0, 1.0 - (distance / max(len(predicted), len(reference))))


def _normalize_for_character_accuracy(text: str) -> str:
    return normalize_text(text).replace(" ", "").replace("\n", "")


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insertion = current[right_index - 1] + 1
            deletion = previous[right_index] + 1
            substitution = previous[right_index - 1] + (0 if left_char == right_char else 1)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]
