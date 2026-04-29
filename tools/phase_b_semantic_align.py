from __future__ import annotations

import argparse
import bisect
import json
import re
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


_BETWEEN_RE = re.compile(r"between\(t,([0-9]+(?:\.[0-9]+)?),([0-9]+(?:\.[0-9]+)?)\)")
_GAMEPLAY_PROMPT_RE = re.compile(r"(查看|按住|跳跃|冲刺|翻滚|招架|攻击|防御)")
_LEADING_SPEAKER_RE = re.compile(r"^[^：:\s]{1,8}[：:]\s*")
_EN_SPEAKER_RE = re.compile(r"[A-Z][A-Za-z' .-]{0,30}:\s")
_EN_ALL_CAPS_RE = re.compile(r"^[A-Z0-9 '&:,.!?-]+$")


@dataclass(slots=True)
class ChineseCue:
    clip_name: str
    index: int
    start: float
    end: float
    text: str
    confidence: float


@dataclass(slots=True)
class ChineseClip:
    clip_name: str
    duration: float
    cues: list[ChineseCue]


@dataclass(slots=True)
class EnglishSegment:
    part_name: str
    index: int
    segment_id: str
    start: float
    end: float
    text: str


@dataclass(slots=True)
class CutInterval:
    original_start: float
    original_end: float
    cut_start: float
    cut_end: float


@dataclass(slots=True)
class EnglishPart:
    part_name: str
    transcript_path: Path
    video_path: Path
    video_duration: float
    cut_source: str
    cut_intervals: list[CutInterval]
    segments: list[EnglishSegment]


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase B cut-time + semantic alignment.")
    parser.add_argument("--ocr-root", type=Path, required=True)
    parser.add_argument("--english-ocr-root", type=Path)
    parser.add_argument("--video-root", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-name", type=str, default="paraphrase-multilingual-MiniLM-L12-v2")
    parser.add_argument("--mode", choices=["mapping", "full"], default="full")
    parser.add_argument("--window-size", type=int, default=18)
    parser.add_argument("--window-stride", type=int, default=6)
    parser.add_argument("--segment-match-threshold", type=float, default=0.36)
    parser.add_argument("--time-margin", type=float, default=3.0)
    parser.add_argument("--time-candidate-seconds", type=float, default=18.0)
    parser.add_argument("--cue-index-radius", type=int, default=24)
    parser.add_argument("--context-window", type=int, default=2)
    parser.add_argument("--combined-match-threshold", type=float, default=0.52)
    parser.add_argument("--duration-weight", type=float, default=1.0)
    parser.add_argument("--semantic-weight", type=float, default=0.2)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    clips = load_chinese_clips(args.ocr_root, args.video_root)
    parts = load_english_parts(args.scratch_root, args.english_ocr_root)
    part_order = sorted(parts)

    model = SentenceTransformer(args.model_name)

    clip_signatures = [build_clip_signature(clip.clip_name, clip.duration, clip.cues) for clip in clips]
    window_payloads = build_english_windows(parts, window_size=args.window_size, stride=args.window_stride)
    clip_chunk_payloads = flatten_clip_chunks(clip_signatures)

    window_embeddings = model.encode(
        [item["text"] for item in window_payloads],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
        batch_size=128,
    )
    clip_embeddings = model.encode(
        [item["text"] for item in clip_chunk_payloads],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
        batch_size=64,
    )

    semantic_candidates = score_clip_part_candidates(clip_signatures, clip_chunk_payloads, clip_embeddings, window_payloads, window_embeddings)
    save_json(args.output_dir / "clip_part_candidates.json", {"clips": semantic_candidates})

    assignment_payload = assign_clips_to_parts(
        clips=clips,
        parts=parts,
        part_order=part_order,
        semantic_candidates=semantic_candidates,
        duration_weight=args.duration_weight,
        semantic_weight=args.semantic_weight,
    )
    save_json(args.output_dir / "clip_part_mapping.json", assignment_payload)

    if args.mode == "mapping":
        print(json.dumps({"mode": "mapping", "clip_count": len(clips), "part_count": len(parts)}, ensure_ascii=False, indent=2))
        return

    bilingual_payload = build_bilingual_alignment(
        model=model,
        parts=parts,
        clips=clips,
        assignment_payload=assignment_payload,
        time_margin=args.time_margin,
        time_candidate_seconds=args.time_candidate_seconds,
        cue_index_radius=args.cue_index_radius,
        context_window=args.context_window,
        combined_match_threshold=args.combined_match_threshold,
        segment_match_threshold=args.segment_match_threshold,
    )
    save_json(args.output_dir / "bilingual_alignment.preliminary.json", bilingual_payload)
    print(json.dumps({"mode": "full", "clip_count": len(clips), "part_count": len(parts)}, ensure_ascii=False, indent=2))


def load_chinese_clips(ocr_root: Path, video_root: Path) -> list[ChineseClip]:
    clips: list[ChineseClip] = []
    for clip_dir in sorted(path for path in ocr_root.iterdir() if path.is_dir()):
        cleaned_path = clip_dir / "cleaned.json"
        if not cleaned_path.exists():
            continue
        payload = json.loads(cleaned_path.read_text(encoding="utf-8-sig"))
        video_path = video_root / f"{clip_dir.name}.mp4"
        if not video_path.exists():
            raise FileNotFoundError(f"Missing source clip for {clip_dir.name}: {video_path}")
        cues: list[ChineseCue] = []
        for item in payload.get("cues") or []:
            cues.append(
                ChineseCue(
                    clip_name=clip_dir.name,
                    index=int(item.get("index") or 0),
                    start=float(item.get("start") or 0.0),
                    end=float(item.get("end") or 0.0),
                    text=str(item.get("text") or "").strip(),
                    confidence=float(item.get("confidence") or 0.0),
                )
            )
        clips.append(ChineseClip(clip_name=clip_dir.name, duration=probe_duration(video_path), cues=cues))
    return clips


def load_english_parts(scratch_root: Path, english_ocr_root: Path | None = None) -> dict[str, EnglishPart]:
    parts: dict[str, EnglishPart] = {}
    for part_dir in sorted(path for path in scratch_root.glob("ghost-yotei-part*") if path.is_dir()):
        video_path = pick_part_video_path(part_dir)
        video_duration = probe_duration(video_path)
        ocr_cleaned_path = pick_english_ocr_path(english_ocr_root, part_dir.name) if english_ocr_root else None
        if ocr_cleaned_path is not None:
            transcript_path = ocr_cleaned_path
            segments = load_english_segments_from_ocr(part_dir.name, ocr_cleaned_path)
            cut_source = "english-ocr"
            cut_intervals = annotate_cut_intervals([(0.0, video_duration)])
        else:
            transcript_path = pick_transcript_path(part_dir)
            if transcript_path is None:
                continue
            segments = load_english_segments(part_dir.name, transcript_path)
            cut_source, cut_intervals = choose_cut_intervals(part_dir, segments, video_duration)
        parts[part_dir.name] = EnglishPart(
            part_name=part_dir.name,
            transcript_path=transcript_path,
            video_path=video_path,
            video_duration=video_duration,
            cut_source=cut_source,
            cut_intervals=cut_intervals,
            segments=segments,
        )
    return parts


def pick_english_ocr_path(english_ocr_root: Path | None, part_name: str) -> Path | None:
    if english_ocr_root is None:
        return None
    short_name = part_name.replace("ghost-yotei-", "")
    candidate = english_ocr_root / short_name / "cleaned.json"
    return candidate if candidate.exists() else None


def pick_transcript_path(part_dir: Path) -> Path | None:
    candidates = sorted(part_dir.glob("transcript*.json"))
    if not candidates:
        return None
    ranked = sorted(candidates, key=_transcript_quality_key, reverse=True)
    return ranked[0]


def pick_part_video_path(part_dir: Path) -> Path:
    candidates = sorted(path for path in part_dir.glob("*.mp4") if "dialogue-cut" in path.name.lower())
    if not candidates:
        raise FileNotFoundError(f"No dialogue-cut video found under {part_dir}")

    def key(path: Path) -> tuple[int, int]:
        lowered = path.name.lower()
        priority = 0
        if ".fixed.mp4" in lowered:
            priority += 4
        if "tight" in lowered:
            priority += 3
        if "cq30" in lowered:
            priority += 2
        if "vad-g3" in lowered or "whisper-vad" in lowered:
            priority += 1
        return (priority, int(path.stat().st_size))

    return max(candidates, key=key)


def load_english_segments(part_name: str, transcript_path: Path) -> list[EnglishSegment]:
    payload = json.loads(transcript_path.read_text(encoding="utf-8-sig"))
    segments = payload.get("Segments") or payload.get("segments") or []
    results: list[EnglishSegment] = []
    for index, item in enumerate(segments, start=1):
        results.append(
            EnglishSegment(
                part_name=part_name,
                index=index,
                segment_id=str(item.get("Id") or item.get("id") or f"{part_name}_{index:05d}"),
                start=float(item.get("Start") or item.get("start") or 0.0),
                end=float(item.get("End") or item.get("end") or item.get("Start") or item.get("start") or 0.0),
                text=str(item.get("Text") or item.get("text") or "").strip(),
            )
        )
    return results


def load_english_segments_from_ocr(part_name: str, cleaned_json_path: Path) -> list[EnglishSegment]:
    payload = json.loads(cleaned_json_path.read_text(encoding="utf-8-sig"))
    results: list[EnglishSegment] = []
    for index, item in enumerate(payload.get("cues") or [], start=1):
        results.append(
            EnglishSegment(
                part_name=part_name,
                index=index,
                segment_id=str(item.get("id") or f"{part_name}_{index:05d}"),
                start=float(item.get("start") or 0.0),
                end=float(item.get("end") or item.get("start") or 0.0),
                text=str(item.get("text") or "").strip(),
            )
        )
    return results


def choose_cut_intervals(part_dir: Path, segments: list[EnglishSegment], video_duration: float) -> tuple[str, list[CutInterval]]:
    transcript_intervals = merge_intervals((segment.start, segment.end) for segment in segments if segment.end > segment.start)
    filter_path = pick_filter_path(part_dir)
    filter_intervals = parse_filter_intervals(filter_path) if filter_path else []

    candidates: list[tuple[str, list[tuple[float, float]], float]] = []
    if transcript_intervals:
        candidates.append(("transcript", transcript_intervals, interval_duration(transcript_intervals)))
    if filter_intervals:
        candidates.append(("filter", filter_intervals, interval_duration(filter_intervals)))
    if not candidates:
        raise ValueError(f"No cut intervals available for {part_dir}")

    source, intervals, _ = min(candidates, key=lambda item: abs(item[2] - video_duration))
    return source, annotate_cut_intervals(intervals)


def pick_filter_path(part_dir: Path) -> Path | None:
    preferred = sorted(path for path in part_dir.glob("*.filter.txt") if "audio-concat" not in path.name.lower())
    if preferred:
        return preferred[0]
    fallback = sorted(part_dir.glob("*.filter.txt"))
    return fallback[0] if fallback else None


def parse_filter_intervals(path: Path) -> list[tuple[float, float]]:
    text = path.read_text(encoding="utf-8-sig")
    intervals = [(float(start), float(end)) for start, end in _BETWEEN_RE.findall(text)]
    return merge_intervals(intervals)


def merge_intervals(intervals: Any) -> list[tuple[float, float]]:
    normalized = sorted((float(start), float(end)) for start, end in intervals if float(end) > float(start))
    merged: list[list[float]] = []
    for start, end in normalized:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def annotate_cut_intervals(intervals: list[tuple[float, float]]) -> list[CutInterval]:
    cut_cursor = 0.0
    annotated: list[CutInterval] = []
    for start, end in intervals:
        duration = end - start
        annotated.append(
            CutInterval(
                original_start=start,
                original_end=end,
                cut_start=cut_cursor,
                cut_end=cut_cursor + duration,
            )
        )
        cut_cursor += duration
    return annotated


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def build_clip_signature(clip_name: str, clip_duration: float, cues: list[ChineseCue]) -> dict[str, Any]:
    semantic_entries = build_semantic_entries(cues)
    if not semantic_entries:
        semantic_entries = build_semantic_entries(cues, allow_gameplay=True)

    head = semantic_entries[:15]
    middle_start = max(0, (len(semantic_entries) // 2) - 7)
    middle = semantic_entries[middle_start : middle_start + 15]
    tail = semantic_entries[-15:]

    chunks = []
    for chunk_name, chunk_entries in [("head", head), ("middle", middle), ("tail", tail)]:
        deduped = dedupe_ordered([entry["text"] for entry in chunk_entries])
        if not deduped:
            continue
        chunk_start = min(float(entry["start"]) for entry in chunk_entries)
        chunk_end = max(float(entry["end"]) for entry in chunk_entries)
        chunk_mid = (chunk_start + chunk_end) * 0.5
        duration_denom = max(clip_duration, 1e-6)
        chunks.append(
            {
                "name": chunk_name,
                "text": " ".join(deduped)[:1800],
                "start_seconds": round(chunk_start, 3),
                "end_seconds": round(chunk_end, 3),
                "mid_seconds": round(chunk_mid, 3),
                "start_ratio": round(chunk_start / duration_denom, 6),
                "mid_ratio": round(chunk_mid / duration_denom, 6),
            }
        )

    deduped = dedupe_ordered([entry["text"] for entry in (head + middle + tail)])
    return {
        "clip_name": clip_name,
        "text": " ".join(deduped)[:4000],
        "cue_count": len(cues),
        "semantic_text_count": len(semantic_entries),
        "chunks": chunks,
    }


def build_semantic_entries(cues: list[ChineseCue], allow_gameplay: bool = False) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for cue in cues:
        text = prepare_chinese_text(cue.text, allow_gameplay=allow_gameplay)
        if not text:
            continue
        entries.append(
            {
                "text": text,
                "start": cue.start,
                "end": cue.end,
                "cue_index": cue.index,
            }
        )
    return entries


def prepare_chinese_text(text: str, allow_gameplay: bool = False) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""
    normalized = _LEADING_SPEAKER_RE.sub("", normalized)
    normalized = normalized.replace("·", "").replace("...", " ")
    normalized = normalized.strip("，。！？：: ")
    if not normalized:
        return ""
    if not allow_gameplay and _GAMEPLAY_PROMPT_RE.search(normalized) and len(normalized) <= 8:
        return ""
    return normalized


def prepare_english_text(text: str) -> str:
    normalized = normalize_text(text)
    normalized = normalized.replace("[speech]", "").strip()
    normalized = re.sub(r"\s+", " ", normalized)
    speaker_match = _EN_SPEAKER_RE.search(normalized)
    if speaker_match and speaker_match.start() > 0:
        prefix = normalized[: speaker_match.start()].strip(" -|")
        if prefix and (prefix.upper() == prefix or "task" in prefix.lower()):
            normalized = normalized[speaker_match.start() :].strip()
    word_count = len([word for word in normalized.split(" ") if word])
    if ":" not in normalized and word_count <= 6 and normalized.upper() == normalized and _EN_ALL_CAPS_RE.fullmatch(normalized):
        return ""
    return normalized


def build_english_windows(parts: dict[str, EnglishPart], window_size: int, stride: int) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for part_name in sorted(parts):
        part = parts[part_name]
        selected = [
            (segment.index - 1, segment)
            for segment in part.segments
            if interval_overlaps_cut(part.cut_intervals, segment.start, segment.end)
        ]
        cleaned = [prepare_english_text(segment.text) for _, segment in selected]
        for start_index in range(0, len(selected), stride):
            end_index = min(len(selected), start_index + window_size)
            slice_segments = selected[start_index:end_index]
            texts = [cleaned[idx] for idx in range(start_index, end_index) if cleaned[idx]]
            if not texts:
                continue
            windows.append(
                {
                    "part_name": part_name,
                    "start_index": slice_segments[0][0],
                    "end_index": slice_segments[-1][0],
                    "start_time": slice_segments[0][1].start,
                    "end_time": slice_segments[-1][1].end,
                    "text": " ".join(texts)[:4000],
                }
            )
    return windows


def flatten_clip_chunks(clip_signatures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for clip_index, signature in enumerate(clip_signatures):
        for chunk_index, chunk in enumerate(signature["chunks"]):
            payloads.append(
                {
                    "clip_index": clip_index,
                    "clip_name": signature["clip_name"],
                    "chunk_index": chunk_index,
                    "chunk_name": chunk["name"],
                    "text": chunk["text"],
                    "chunk_start_seconds": float(chunk["start_seconds"]),
                    "chunk_end_seconds": float(chunk["end_seconds"]),
                    "chunk_mid_seconds": float(chunk["mid_seconds"]),
                    "chunk_start_ratio": float(chunk["start_ratio"]),
                    "chunk_mid_ratio": float(chunk["mid_ratio"]),
                }
            )
    return payloads


def score_clip_part_candidates(
    clip_signatures: list[dict[str, Any]],
    clip_chunk_payloads: list[dict[str, Any]],
    clip_embeddings: np.ndarray,
    windows: list[dict[str, Any]],
    window_embeddings: np.ndarray,
) -> list[dict[str, Any]]:
    chunk_scores_by_clip: dict[int, list[tuple[dict[str, Any], np.ndarray]]] = {}
    for payload, embedding in zip(clip_chunk_payloads, clip_embeddings):
        chunk_scores_by_clip.setdefault(int(payload["clip_index"]), []).append((payload, np.matmul(window_embeddings, embedding)))

    mapping: list[dict[str, Any]] = []
    for clip_index, signature in enumerate(clip_signatures):
        chunk_entries = chunk_scores_by_clip.get(clip_index, [])
        candidates = aggregate_chunk_candidates(chunk_entries, windows)
        best = candidates[0] if candidates else {"part_name": "", "score": 0.0}
        mapping.append(
            {
                "clip_name": signature["clip_name"],
                "selected_part": best["part_name"],
                "selected_score": best["score"],
                "part_scores": {item["part_name"]: item["score"] for item in candidates},
                "candidates": candidates,
            }
        )
    return mapping


def aggregate_chunk_candidates(
    chunk_entries: list[tuple[dict[str, Any], np.ndarray]],
    windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    per_part: dict[str, dict[str, Any]] = {}
    for payload, scores in chunk_entries:
        best_per_part: dict[str, tuple[int, float]] = {}
        for window_index in np.argsort(scores)[::-1][:40]:
            score = float(scores[int(window_index)])
            window = windows[int(window_index)]
            current = best_per_part.get(window["part_name"])
            if current is None or score > current[1]:
                best_per_part[window["part_name"]] = (int(window_index), score)
        for part_name, (window_index, score) in best_per_part.items():
            window = windows[window_index]
            entry = per_part.setdefault(
                part_name,
                {
                    "part_name": part_name,
                    "scores": [],
                    "windows": [],
                    "chunk_matches": [],
                },
            )
            entry["scores"].append(score)
            entry["windows"].append(window)
            entry["chunk_matches"].append(
                {
                    "chunk_name": payload["chunk_name"],
                    "chunk_start_seconds": round(float(payload["chunk_start_seconds"]), 3),
                    "chunk_end_seconds": round(float(payload["chunk_end_seconds"]), 3),
                    "chunk_mid_seconds": round(float(payload["chunk_mid_seconds"]), 3),
                    "chunk_start_ratio": round(float(payload["chunk_start_ratio"]), 6),
                    "chunk_mid_ratio": round(float(payload["chunk_mid_ratio"]), 6),
                    "window_start_time": round(float(window["start_time"]), 3),
                    "window_end_time": round(float(window["end_time"]), 3),
                    "score": round(score, 4),
                }
            )

    candidates: list[dict[str, Any]] = []
    for part_name, entry in per_part.items():
        if not entry["scores"]:
            continue
        representative = select_representative_window(entry["windows"])
        spread = max(window["start_time"] for window in entry["windows"]) - min(window["start_time"] for window in entry["windows"])
        spread_penalty = min(0.06, spread / 20000.0)
        score = (sum(entry["scores"]) / len(entry["scores"])) + (0.02 * len(entry["scores"])) - spread_penalty
        candidates.append(
            {
                "part_name": part_name,
                "window_start_index": representative["start_index"],
                "window_end_index": representative["end_index"],
                "window_start_time": round(float(representative["start_time"]), 3),
                "window_end_time": round(float(representative["end_time"]), 3),
                "score": round(float(score), 4),
                "chunk_hit_count": len(entry["scores"]),
                "window_count": len(entry["windows"]),
                "time_spread_seconds": round(float(spread), 3),
                "chunk_matches": sorted(entry["chunk_matches"], key=lambda item: (-float(item["score"]), item["chunk_mid_seconds"]))[:8],
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["part_name"], item["window_start_time"]))
    return candidates[:8]


def select_representative_window(windows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(windows) == 1:
        return windows[0]
    starts = sorted(window["start_time"] for window in windows)
    median_start = statistics.median(starts)
    return min(windows, key=lambda item: abs(item["start_time"] - median_start))


def assign_clips_to_parts(
    clips: list[ChineseClip],
    parts: dict[str, EnglishPart],
    part_order: list[str],
    semantic_candidates: list[dict[str, Any]],
    duration_weight: float,
    semantic_weight: float,
) -> dict[str, Any]:
    prefix = [0.0]
    for clip in clips:
        prefix.append(prefix[-1] + clip.duration)

    semantic_by_clip = {item["clip_name"]: item for item in semantic_candidates}
    memo: dict[tuple[int, int], tuple[float, list[tuple[int, int]] | None]] = {}

    def group_duration(start: int, end: int) -> float:
        return prefix[end] - prefix[start]

    def solve(clip_index: int, part_index: int) -> tuple[float, list[tuple[int, int]] | None]:
        key = (clip_index, part_index)
        if key in memo:
            return memo[key]
        if part_index == len(part_order):
            if clip_index == len(clips):
                memo[key] = (0.0, [])
            else:
                memo[key] = (10**9, None)
            return memo[key]

        best_cost = 10**9
        best_path: list[tuple[int, int]] | None = None
        remaining_parts = len(part_order) - part_index
        upper = len(clips) - (remaining_parts - 1)
        for end_index in range(clip_index + 1, upper + 1):
            duration = group_duration(clip_index, end_index)
            target = parts[part_order[part_index]].cut_intervals[-1].cut_end
            duration_error = abs(duration - target) / max(target, 1.0)
            semantic_score = average_semantic_score(clips[clip_index:end_index], part_order[part_index], semantic_by_clip)
            group_cost = (duration_weight * (duration_error**2)) - (semantic_weight * semantic_score)

            next_cost, next_path = solve(end_index, part_index + 1)
            if next_path is None:
                continue
            total_cost = group_cost + next_cost
            if total_cost < best_cost:
                best_cost = total_cost
                best_path = [(clip_index, end_index)] + next_path

        memo[key] = (best_cost, best_path)
        return memo[key]

    total_cost, partitions = solve(0, 0)
    if partitions is None:
        raise RuntimeError("Unable to partition clips onto ordered parts.")

    assignments: list[dict[str, Any]] = []
    part_summaries: list[dict[str, Any]] = []
    for part_name, (start_index, end_index) in zip(part_order, partitions):
        part = parts[part_name]
        part_duration = part.cut_intervals[-1].cut_end
        group_clips = clips[start_index:end_index]
        group_duration_seconds = sum(clip.duration for clip in group_clips)
        scale = (part_duration / group_duration_seconds) if group_duration_seconds > 0 else 1.0
        clip_names: list[str] = []
        remaining_by_index: list[float] = []
        remaining_after = 0.0
        normalized_durations = [clip.duration * scale for clip in group_clips]
        for value in reversed(normalized_durations):
            remaining_by_index.append(remaining_after)
            remaining_after += value
        remaining_by_index.reverse()
        clip_cursor = 0.0
        for order_index, clip in enumerate(group_clips, start=1):
            normalized_cut_duration = normalized_durations[order_index - 1]
            semantic = semantic_by_clip[clip.clip_name]
            anchor_start = estimate_clip_cut_start(
                part_name=part_name,
                semantic=semantic,
                normalized_cut_duration=normalized_cut_duration,
            )
            max_start = max(0.0, part_duration - (normalized_cut_duration + remaining_by_index[order_index - 1]))
            proposed_start = anchor_start if anchor_start is not None else clip_cursor
            cut_start = min(max(proposed_start, clip_cursor), max_start)
            cut_end = cut_start + normalized_cut_duration
            clip_cursor = cut_end
            clip_names.append(clip.clip_name)
            assigned_score = float(semantic.get("part_scores", {}).get(part_name, 0.0))
            best_alt = max(
                (float(score) for candidate_part, score in semantic.get("part_scores", {}).items() if candidate_part != part_name),
                default=0.0,
            )
            assignments.append(
                {
                    "clip_name": clip.clip_name,
                    "assigned_part": part_name,
                    "clip_order_in_part": order_index,
                    "clip_duration": round(clip.duration, 3),
                    "normalized_cut_duration": round(normalized_cut_duration, 3),
                    "cut_scale": round(scale, 6),
                    "part_cut_start": round(cut_start, 3),
                    "part_cut_end": round(cut_end, 3),
                    "approx_original_start": round(cut_time_to_original(part.cut_intervals, cut_start), 3),
                    "approx_original_end": round(cut_time_to_original(part.cut_intervals, min(cut_end, part_duration)), 3),
                    "semantic_assigned_score": round(assigned_score, 4),
                    "semantic_best_alternative_score": round(best_alt, 4),
                    "semantic_anchor_cut_start": round(anchor_start, 3) if anchor_start is not None else None,
                    "semantic_candidates": semantic["candidates"],
                }
            )
        part_summaries.append(
            {
                "part_name": part_name,
                "clip_count": len(group_clips),
                "clip_names": clip_names,
                "cut_duration_target": round(part_duration, 3),
                "assigned_clip_duration": round(group_duration_seconds, 3),
                "duration_gap_seconds": round(group_duration_seconds - part_duration, 3),
                "cut_source": part.cut_source,
                "transcript_path": str(part.transcript_path),
                "video_path": str(part.video_path),
            }
        )

    return {
        "version": "0.2",
        "partition_cost": round(total_cost, 6),
        "parts": part_summaries,
        "clips": assignments,
    }


def estimate_clip_cut_start(part_name: str, semantic: dict[str, Any], normalized_cut_duration: float) -> float | None:
    estimates: list[tuple[float, float]] = []
    for candidate in semantic.get("candidates") or []:
        if str(candidate.get("part_name")) != part_name:
            continue
        for match in candidate.get("chunk_matches") or []:
            center_time = (float(match["window_start_time"]) + float(match["window_end_time"])) * 0.5
            center_ratio = float(match.get("chunk_mid_ratio") or 0.0)
            estimate = center_time - (center_ratio * normalized_cut_duration)
            estimates.append((estimate, float(match.get("score") or 0.0)))
    if not estimates:
        return None
    estimates.sort(key=lambda item: item[0])
    total_weight = sum(max(weight, 1e-6) for _, weight in estimates)
    cursor = 0.0
    midpoint = total_weight * 0.5
    for estimate, weight in estimates:
        cursor += max(weight, 1e-6)
        if cursor >= midpoint:
            return max(0.0, estimate)
    return max(0.0, estimates[-1][0])


def average_semantic_score(clips: list[ChineseClip], part_name: str, semantic_by_clip: dict[str, dict[str, Any]]) -> float:
    scores = [float(semantic_by_clip[clip.clip_name].get("part_scores", {}).get(part_name, 0.0)) for clip in clips]
    return sum(scores) / len(scores) if scores else 0.0


def build_bilingual_alignment(
    model: SentenceTransformer,
    parts: dict[str, EnglishPart],
    clips: list[ChineseClip],
    assignment_payload: dict[str, Any],
    time_margin: float,
    time_candidate_seconds: float,
    cue_index_radius: int,
    context_window: int,
    combined_match_threshold: float,
    segment_match_threshold: float,
) -> dict[str, Any]:
    clip_lookup = {clip.clip_name: clip for clip in clips}
    assignments_by_part: dict[str, list[dict[str, Any]]] = {}
    for item in assignment_payload["clips"]:
        assignments_by_part.setdefault(item["assigned_part"], []).append(item)

    per_part_output: list[dict[str, Any]] = []
    per_part_summary: list[dict[str, Any]] = []
    for part_name in sorted(parts):
        part = parts[part_name]
        mapped_cues = collect_mapped_cues(part, assignments_by_part.get(part_name, []), clip_lookup)
        aligned_segments, summary = attach_chinese_to_english_segments(
            model=model,
            part=part,
            mapped_cues=mapped_cues,
            time_margin=time_margin,
            time_candidate_seconds=time_candidate_seconds,
            cue_index_radius=cue_index_radius,
            context_window=context_window,
            combined_match_threshold=combined_match_threshold,
            segment_match_threshold=segment_match_threshold,
        )
        per_part_output.append(
            {
                "part_name": part_name,
                "segment_count": len(aligned_segments),
                "segments": aligned_segments,
            }
        )
        per_part_summary.append(summary)

    return {
        "version": "0.2",
        "alignment_strategy": "cut-time-reconstruction + semantic-time-window",
        "parts": per_part_output,
        "summary": per_part_summary,
    }


def collect_mapped_cues(part: EnglishPart, assignments: list[dict[str, Any]], clip_lookup: dict[str, ChineseClip]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for assignment in sorted(assignments, key=lambda item: item["clip_order_in_part"]):
        clip = clip_lookup[assignment["clip_name"]]
        clip_cut_start = float(assignment["part_cut_start"])
        cut_scale = float(assignment.get("cut_scale") or 1.0)
        for cue in clip.cues:
            semantic_text = prepare_chinese_text(cue.text)
            if not semantic_text:
                continue
            cue_cut_start = clip_cut_start + (cue.start * cut_scale)
            cue_cut_end = clip_cut_start + (cue.end * cut_scale)
            original_start = cut_time_to_original(part.cut_intervals, cue_cut_start)
            original_end = cut_time_to_original(part.cut_intervals, cue_cut_end)
            mapped.append(
                {
                    "clip_name": clip.clip_name,
                    "cue_index": cue.index,
                    "start": cue.start,
                    "end": cue.end,
                    "cut_start": cue_cut_start,
                    "cut_end": cue_cut_end,
                    "original_start": original_start,
                    "original_end": original_end,
                    "text": cue.text,
                    "semantic_text": semantic_text,
                    "confidence": cue.confidence,
                }
            )
    mapped.sort(key=lambda item: (item["cut_start"], item["cut_end"], item["clip_name"], item["cue_index"]))
    for order_index, item in enumerate(mapped):
        item["mapped_order"] = order_index
    return mapped


def attach_chinese_to_english_segments(
    model: SentenceTransformer,
    part: EnglishPart,
    mapped_cues: list[dict[str, Any]],
    time_margin: float,
    time_candidate_seconds: float,
    cue_index_radius: int,
    context_window: int,
    combined_match_threshold: float,
    segment_match_threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    usable_segments = build_english_alignment_units(part)
    output_segments = [
        {
            "id": segment["segment_id"],
            "segment_ids": segment["segment_ids"],
            "start": round(segment["start"], 3),
            "end": round(segment["end"], 3),
            "english_text": segment["text"],
            "chinese_text": "",
            "match_score": None,
            "source_clip": None,
            "source_cue_index": None,
        }
        for segment in usable_segments
    ]
    usable_cues = [cue for cue in mapped_cues if cue["semantic_text"]]

    if not usable_segments or not usable_cues:
        return (
            output_segments,
            {
                "part_name": part.part_name,
                "segment_count": len(output_segments),
                "mapped_cue_count": len(mapped_cues),
                "matched_segment_count": 0,
            },
        )

    cue_context_texts = build_context_texts(
        [item["semantic_text"] for item in usable_cues],
        radius=max(1, context_window // 2),
        max_chars=160,
    )
    segment_context_texts = build_context_texts(
        [item["semantic_text"] for item in usable_segments],
        radius=context_window,
        max_chars=220,
    )

    cue_embeddings = model.encode(
        [item["semantic_text"] for item in usable_cues],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=256,
    )
    cue_context_embeddings = model.encode(
        cue_context_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=256,
    )
    segment_embeddings = model.encode(
        [item["semantic_text"] for item in usable_segments],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=256,
    )
    segment_context_embeddings = model.encode(
        segment_context_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=256,
    )

    pair_candidates: list[dict[str, Any]] = []
    cue_centers = [((item["cut_start"] + item["cut_end"]) / 2.0) for item in usable_cues]
    for segment_row, segment in enumerate(usable_segments):
        segment_center = float(segment["center"])
        nearest_index = nearest_center_index(cue_centers, segment_center)
        left = max(0, nearest_index - cue_index_radius)
        right = min(len(usable_cues), nearest_index + cue_index_radius + 1)
        candidate_indices = []
        for cue_index in range(left, right):
            cue = usable_cues[cue_index]
            overlap = overlap_seconds(segment["cut_start"], segment["cut_end"], cue["cut_start"], cue["cut_end"])
            center_distance = abs(segment_center - cue_centers[cue_index])
            if overlap > 0.0 or center_distance <= max(time_candidate_seconds, time_margin):
                candidate_indices.append(cue_index)
        if not candidate_indices:
            continue
        base_scores = np.matmul(cue_embeddings[candidate_indices], segment_embeddings[segment_row])
        context_scores = np.matmul(cue_context_embeddings[candidate_indices], segment_context_embeddings[segment_row])
        for offset, cue_index in enumerate(candidate_indices):
            cue = usable_cues[cue_index]
            base_score = float(base_scores[offset])
            context_score = float(context_scores[offset])
            center_distance = abs(segment_center - cue_centers[cue_index])
            time_score = max(0.0, 1.0 - (center_distance / max(time_candidate_seconds, 1.0)))
            confidence_bonus = max(0.0, min(float(cue["confidence"]), 1.0) - 0.75) * 0.2
            score = (0.5 * context_score) + (0.25 * base_score) + (0.2 * time_score) + (0.05 * confidence_bonus)
            if base_score < segment_match_threshold and context_score < (segment_match_threshold + 0.04):
                continue
            if score < combined_match_threshold:
                continue
            pair_candidates.append(
                {
                    "segment_index": segment["segment_index"],
                    "segment_id": segment["segment_id"],
                    "segment_start": segment["start"],
                    "segment_end": segment["end"],
                    "cue_key": f"{cue['clip_name']}::{cue['cue_index']}",
                    "cue_order": cue["mapped_order"],
                    "cue_text": cue["text"],
                    "cue_clip": cue["clip_name"],
                    "cue_index": cue["cue_index"],
                    "score": round(score, 4),
                    "base_score": round(base_score, 4),
                    "context_score": round(context_score, 4),
                    "time_score": round(time_score, 4),
                }
            )

    selected_pairs = select_monotonic_segment_pairs(pair_candidates)
    for pair in selected_pairs:
        target = output_segments[int(pair["segment_index"])]
        target["chinese_text"] = pair["cue_text"]
        target["match_score"] = pair["score"]
        target["source_clip"] = pair["cue_clip"]
        target["source_cue_index"] = pair["cue_index"]

    return (
        output_segments,
            {
                "part_name": part.part_name,
                "segment_count": len(output_segments),
                "mapped_cue_count": len(mapped_cues),
                "matched_segment_count": len(selected_pairs),
                "mean_match_score": round(sum(float(item["score"]) for item in selected_pairs) / len(selected_pairs), 4)
                if selected_pairs
                else None,
            },
        )


def select_monotonic_segment_pairs(pair_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for candidate in pair_candidates:
        grouped.setdefault(int(candidate["segment_index"]), []).append(candidate)

    selected: list[dict[str, Any]] = []
    used_cues: set[str] = set()
    last_cue_order = -1
    for segment_index in sorted(grouped):
        choices = sorted(
            grouped[segment_index],
            key=lambda item: (-float(item["score"]), -float(item.get("context_score", 0.0)), int(item["cue_order"])),
        )
        chosen = None
        for candidate in choices:
            cue_key = str(candidate["cue_key"])
            cue_order = int(candidate["cue_order"])
            if cue_key in used_cues or cue_order <= last_cue_order:
                continue
            chosen = candidate
            break
        if chosen is None:
            continue
        selected.append(chosen)
        used_cues.add(str(chosen["cue_key"]))
        last_cue_order = int(chosen["cue_order"])
    return selected


def build_english_alignment_units(part: EnglishPart) -> list[dict[str, Any]]:
    raw_segments = [
        {
            "raw_segment_index": segment.index - 1,
            "segment_id": segment.segment_id,
            "start": segment.start,
            "end": segment.end,
            "cut_ranges": cut_ranges,
            "cut_start": cut_ranges[0][0],
            "cut_end": cut_ranges[-1][1],
            "text": segment.text,
            "semantic_text": prepared_text,
        }
        for segment in part.segments
        for prepared_text in [prepare_english_text(segment.text)]
        for cut_ranges in [original_interval_to_cut_ranges(part.cut_intervals, segment.start, segment.end)]
        if prepared_text and cut_ranges
    ]

    units: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for item in raw_segments:
        if current is None:
            current = {
                "segment_indices": [item["raw_segment_index"]],
                "segment_ids": [item["segment_id"]],
                "start": item["start"],
                "end": item["end"],
                "cut_start": item["cut_start"],
                "cut_end": item["cut_end"],
                "texts": [item["semantic_text"]],
            }
            continue

        can_merge = (
            (item["start"] - float(current["end"]) <= 0.85)
            and (item["cut_start"] - float(current["cut_end"]) <= 0.85)
            and ((item["end"] - float(current["start"])) <= 8.0)
            and (sum(len(text) for text in current["texts"]) + len(item["semantic_text"]) <= 220)
        )
        if can_merge:
            current["segment_indices"].append(item["raw_segment_index"])
            current["segment_ids"].append(item["segment_id"])
            current["end"] = item["end"]
            current["cut_end"] = item["cut_end"]
            current["texts"].append(item["semantic_text"])
            continue

        units.append(finalize_alignment_unit(part.part_name, len(units), current))
        current = {
            "segment_indices": [item["raw_segment_index"]],
            "segment_ids": [item["segment_id"]],
            "start": item["start"],
            "end": item["end"],
            "cut_start": item["cut_start"],
            "cut_end": item["cut_end"],
            "texts": [item["semantic_text"]],
        }

    if current is not None:
        units.append(finalize_alignment_unit(part.part_name, len(units), current))
    return units


def finalize_alignment_unit(part_name: str, unit_index: int, current: dict[str, Any]) -> dict[str, Any]:
    segment_ids = [str(item) for item in current["segment_ids"]]
    unit_id = segment_ids[0] if len(segment_ids) == 1 else f"{part_name}_blk_{unit_index + 1:04d}"
    merged_text = " ".join(str(text) for text in current["texts"] if text).strip()
    return {
        "segment_index": unit_index,
        "segment_id": unit_id,
        "segment_ids": segment_ids,
        "start": float(current["start"]),
        "end": float(current["end"]),
        "cut_start": float(current["cut_start"]),
        "cut_end": float(current["cut_end"]),
        "text": merged_text,
        "semantic_text": prepare_english_text(merged_text),
        "center": ((float(current["cut_start"]) + float(current["cut_end"])) / 2.0),
    }


def interval_overlaps_cut(cut_intervals: list[CutInterval], start: float, end: float) -> bool:
    return any(overlap_seconds(interval.original_start, interval.original_end, start, end) > 0.0 for interval in cut_intervals)


def build_context_texts(items: list[str], radius: int, max_chars: int) -> list[str]:
    outputs: list[str] = []
    for index in range(len(items)):
        start = max(0, index - radius)
        end = min(len(items), index + radius + 1)
        merged = " ".join(text for text in items[start:end] if text)
        outputs.append(merged[:max_chars] if merged else items[index])
    return outputs


def nearest_center_index(sorted_centers: list[float], target: float) -> int:
    if not sorted_centers:
        return 0
    position = bisect.bisect_left(sorted_centers, target)
    if position <= 0:
        return 0
    if position >= len(sorted_centers):
        return len(sorted_centers) - 1
    left = sorted_centers[position - 1]
    right = sorted_centers[position]
    return position if abs(right - target) < abs(target - left) else (position - 1)


def original_interval_to_cut_ranges(intervals: list[CutInterval], original_start: float, original_end: float) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    for interval in intervals:
        overlap_start = max(original_start, interval.original_start)
        overlap_end = min(original_end, interval.original_end)
        if overlap_end <= overlap_start:
            continue
        cut_start = interval.cut_start + (overlap_start - interval.original_start)
        cut_end = interval.cut_start + (overlap_end - interval.original_start)
        ranges.append((cut_start, cut_end))
    return ranges


def cut_time_to_original(intervals: list[CutInterval], cut_time: float) -> float:
    if not intervals:
        return cut_time
    bounded = min(max(cut_time, 0.0), intervals[-1].cut_end)
    for interval in intervals:
        if bounded <= interval.cut_end:
            offset = bounded - interval.cut_start
            return interval.original_start + max(0.0, min(offset, interval.original_end - interval.original_start))
    return intervals[-1].original_end


def interval_duration(intervals: list[tuple[float, float]]) -> float:
    return sum(end - start for start, end in intervals)


def overlap_seconds(left_start: float, left_end: float, right_start: float, right_end: float) -> float:
    return max(0.0, min(left_end, right_end) - max(left_start, right_start))


def normalize_text(text: str) -> str:
    normalized = text.replace("|", "丨").replace("…", "...")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def dedupe_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _transcript_quality_key(path: Path) -> tuple[float, float, float]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    segments = payload.get("Segments") or payload.get("segments") or []
    if not segments:
        return (-1.0, -1.0, _name_priority(path.name))

    usable_texts = []
    for item in segments:
        text = prepare_english_text(str(item.get("Text") or item.get("text") or ""))
        if not text or text == "[speech]":
            continue
        usable_texts.append(text)

    usable_ratio = len(usable_texts) / len(segments)
    average_length = (sum(len(text) for text in usable_texts) / len(usable_texts)) if usable_texts else 0.0
    return (usable_ratio, average_length, _name_priority(path.name))


def _name_priority(name: str) -> float:
    lowered = name.lower()
    score = 0.0
    if "whisper-vad" in lowered:
        score += 5.0
    if "raw-whisper" in lowered:
        score += 4.0
    if "regen" in lowered:
        score += 3.0
    if "tightened" in lowered:
        score += 2.0
    if "vad-g3" in lowered:
        score -= 0.5
    if lowered.endswith("transcript.json"):
        score += 1.0
    return score


if __name__ == "__main__":
    main()
