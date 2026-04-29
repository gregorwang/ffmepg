from __future__ import annotations

import argparse
import csv
import json
import os
import pickle
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from build_phase_b_cue_local_align import align_window as align_group_window
from phase_b_sequence_align import (
    ChineseCue,
    EnglishCue,
    build_context_texts,
    monotonic_align,
    normalize_text,
    prepare_chinese_text,
    prepare_english_text,
    speaker_compatible,
)


DEFAULT_MAPPING_JSON = Path(
    "scratch/phase_b_archive/semantic_sequence_history/phase_b_semantic_v4/clip_part_mapping.json"
)
DEFAULT_CHINESE_OCR_ROOT = Path(r"C:\Users\汪家俊\Downloads\ocr_output_gpu_phasea")
DEFAULT_ENGLISH_OCR_ROOT = Path("scratch/english_ocr_4parts_v1")
DEFAULT_REVIEWED_MASTER_JSON = Path("scratch/phase_b_master_reviewed_v14_round8/all_segments.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_fulltrack_rebuild_v1")
DEFAULT_EMBEDDING_CACHE_DIR = Path("scratch/embedding_cache")


@dataclass(slots=True)
class FullEnglishCue:
    cue_id: str
    part_name: str
    index: int
    start: float
    end: float
    text: str
    semantic_text: str

    @property
    def midpoint(self) -> float:
        return (self.start + self.end) * 0.5


@dataclass(slots=True)
class FullChineseCue:
    clip_name: str
    cue_index: int
    start: float
    end: float
    text: str
    semantic_text: str
    confidence: float


@dataclass(slots=True)
class EmbeddingStore:
    cache_path: Path | None
    vectors: dict[str, np.ndarray]
    cache_hits: int = 0
    cache_misses: int = 0
    save_count: int = 0
    dirty: bool = False

    @classmethod
    def load(cls, cache_path: Path | None) -> "EmbeddingStore":
        if cache_path is None or not cache_path.exists():
            return cls(cache_path=cache_path, vectors={})
        try:
            payload = pickle.loads(cache_path.read_bytes())
        except Exception:
            return cls(cache_path=cache_path, vectors={})
        raw_vectors = payload.get("vectors") if isinstance(payload, dict) else None
        if not isinstance(raw_vectors, dict):
            return cls(cache_path=cache_path, vectors={})
        vectors = {
            str(text): np.asarray(vector, dtype=np.float32)
            for text, vector in raw_vectors.items()
            if str(text)
        }
        return cls(cache_path=cache_path, vectors=vectors)

    def encode(self, model: SentenceTransformer, texts: list[str], batch_size: int) -> np.ndarray:
        ordered = [text for text in texts if text]
        if not ordered:
            return np.empty((0, 0), dtype=np.float32)

        unique = [text for text in dict.fromkeys(ordered)]
        missing = [text for text in unique if text not in self.vectors]
        self.cache_hits += len(unique) - len(missing)
        if missing:
            matrix = model.encode(
                missing,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=batch_size,
            )
            for index, text in enumerate(missing):
                self.vectors[text] = np.asarray(matrix[index], dtype=np.float32)
            self.cache_misses += len(missing)
            self.dirty = True

        dim = int(next(iter(self.vectors.values())).shape[0]) if self.vectors else 0
        outputs = np.empty((len(ordered), dim), dtype=np.float32)
        for index, text in enumerate(ordered):
            outputs[index] = self.vectors[text]
        return outputs

    def save(self) -> None:
        if self.cache_path is None or not self.dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.cache_path.with_suffix(f"{self.cache_path.suffix}.tmp")
        temp_path.write_bytes(
            pickle.dumps(
                {"vectors": self.vectors},
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        )
        temp_path.replace(self.cache_path)
        self.save_count += 1
        self.dirty = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase C full-track draft bilingual subtitles using English OCR cues as the full skeleton."
    )
    parser.add_argument("--mapping-json", type=Path, default=DEFAULT_MAPPING_JSON)
    parser.add_argument("--chinese-ocr-root", type=Path, default=DEFAULT_CHINESE_OCR_ROOT)
    parser.add_argument("--english-ocr-root", type=Path, default=DEFAULT_ENGLISH_OCR_ROOT)
    parser.add_argument("--reviewed-master-json", type=Path, default=DEFAULT_REVIEWED_MASTER_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model-name", type=str, default="paraphrase-multilingual-MiniLM-L12-v2")
    parser.add_argument("--parts", nargs="*", help="Optional part names or short names to rebuild, e.g. ghost-yotei-part02 part03.")
    parser.add_argument("--offline-model-only", action="store_true", help="Use only local model files; do not contact Hugging Face.")
    parser.add_argument("--embedding-cache-dir", type=Path, default=DEFAULT_EMBEDDING_CACHE_DIR)
    parser.add_argument("--disable-embedding-cache", action="store_true", help="Disable on-disk embedding cache.")
    parser.add_argument("--disable-clip-local-first", action="store_true", help="Disable clip-local matching pass before global part-level alignment.")
    parser.add_argument("--context-window", type=int, default=2)
    parser.add_argument("--match-threshold", type=float, default=0.42)
    parser.add_argument("--output-threshold", type=float, default=0.50)
    parser.add_argument("--skip-english-penalty", type=float, default=0.025)
    parser.add_argument("--skip-chinese-penalty", type=float, default=0.018)
    parser.add_argument("--high-threshold", type=float, default=0.82)
    parser.add_argument("--medium-threshold", type=float, default=0.70)
    parser.add_argument("--low-threshold", type=float, default=0.58)
    parser.add_argument("--enable-fallback", action="store_true", help="Enable lower-confidence fallback matching pass.")
    return parser.parse_args()


def part_short_name(part_name: str) -> str:
    return part_name.replace("ghost-yotei-", "")


def sanitize_model_name(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model_name).strip("._-") or "model"


def resolve_local_sentence_model_path(model_name: str) -> Path | None:
    if Path(model_name).exists():
        return Path(model_name)
    candidate_names = [model_name]
    if "/" not in model_name:
        candidate_names.insert(0, f"sentence-transformers/{model_name}")
    for candidate in candidate_names:
        hub_dir = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{candidate.replace('/', '--')}"
        snapshots_dir = hub_dir / "snapshots"
        if not snapshots_dir.exists():
            continue
        snapshots = [path for path in snapshots_dir.iterdir() if path.is_dir()]
        if not snapshots:
            continue
        snapshots.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return snapshots[0]
    return None


def resolve_selected_parts(mapping_parts: list[dict[str, Any]], requested_parts: list[str] | None) -> list[dict[str, Any]]:
    if not requested_parts:
        return mapping_parts

    requested = {item.strip() for item in requested_parts if item and item.strip()}
    matched: list[dict[str, Any]] = []
    unknown = set(requested)
    for part in mapping_parts:
        part_name = str(part["part_name"])
        short_name = part_short_name(part_name)
        if part_name in requested or short_name in requested:
            matched.append(part)
            unknown.discard(part_name)
            unknown.discard(short_name)

    if unknown:
        raise SystemExit(f"unknown parts: {', '.join(sorted(unknown))}")
    return matched


def load_sentence_model(model_name: str, offline_only: bool) -> SentenceTransformer:
    if offline_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        local_path = resolve_local_sentence_model_path(model_name)
        if local_path is None:
            raise SystemExit(f"offline model requested but local snapshot not found for: {model_name}")
        try:
            return SentenceTransformer(str(local_path), local_files_only=True)
        except TypeError:
            return SentenceTransformer(str(local_path))
    try:
        return SentenceTransformer(model_name, local_files_only=offline_only)
    except TypeError:
        return SentenceTransformer(model_name)


def encode_texts(
    model: SentenceTransformer,
    texts: list[str],
    batch_size: int,
    embedding_store: EmbeddingStore | None,
) -> np.ndarray:
    if embedding_store is not None:
        return embedding_store.encode(model=model, texts=texts, batch_size=batch_size)
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    return model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=batch_size,
    )


def load_full_english_cues(english_ocr_root: Path, part_name: str) -> list[FullEnglishCue]:
    short_name = part_short_name(part_name)
    cleaned_path = english_ocr_root / short_name / "cleaned.json"
    payload = json.loads(cleaned_path.read_text(encoding="utf-8-sig"))
    outputs: list[FullEnglishCue] = []
    for raw_index, item in enumerate(payload.get("cues") or [], start=1):
        text = normalize_text(str(item.get("text") or ""))
        cue_id = str(item.get("id") or f"cue_{raw_index:05d}")
        outputs.append(
            FullEnglishCue(
                cue_id=cue_id,
                part_name=part_name,
                index=raw_index,
                start=round(float(item.get("start") or 0.0), 3),
                end=round(float(item.get("end") or 0.0), 3),
                text=text,
                semantic_text=prepare_english_text(text),
            )
        )
    return outputs


def load_full_chinese_cues(chinese_ocr_root: Path, clip_name: str) -> list[FullChineseCue]:
    cleaned_path = chinese_ocr_root / clip_name / "cleaned.json"
    payload = json.loads(cleaned_path.read_text(encoding="utf-8-sig"))
    outputs: list[FullChineseCue] = []
    for item in payload.get("cues") or []:
        text = normalize_text(str(item.get("text") or ""))
        outputs.append(
            FullChineseCue(
                clip_name=clip_name,
                cue_index=int(item.get("index") or 0),
                start=round(float(item.get("start") or 0.0), 3),
                end=round(float(item.get("end") or 0.0), 3),
                text=text,
                semantic_text=prepare_chinese_text(text),
                confidence=round(float(item.get("confidence") or 0.0), 4),
            )
        )
    return outputs


def load_full_chinese_sequence(chinese_ocr_root: Path, clip_names: list[str]) -> list[FullChineseCue]:
    outputs: list[FullChineseCue] = []
    for clip_name in clip_names:
        outputs.extend(load_full_chinese_cues(chinese_ocr_root, clip_name))
    return outputs


def build_anchor_windows(
    reviewed_payload: dict[str, Any],
    part_name: str,
    english_cues: list[FullEnglishCue],
    chinese_sequence: list[FullChineseCue],
) -> list[tuple[int, int, int, int]]:
    english_pos = {cue.cue_id: index for index, cue in enumerate(english_cues)}
    chinese_pos = {(cue.clip_name, cue.cue_index): index for index, cue in enumerate(chinese_sequence)}

    anchors: list[tuple[int, int, int, int]] = []
    for row in reviewed_payload.get("segments") or []:
        if str(row.get("part_name") or "") != part_name:
            continue
        source_clip = str(row.get("source_clip") or "")
        english_ids = [str(item) for item in row.get("english_cue_ids") or []]
        chinese_ids = [int(item) for item in row.get("chinese_cue_ids") or [] if str(item).strip()]
        english_hits = [english_pos[item] for item in english_ids if item in english_pos]
        chinese_hits = [chinese_pos[(source_clip, item)] for item in chinese_ids if (source_clip, item) in chinese_pos]
        if not english_hits or not chinese_hits:
            continue
        anchors.append((min(english_hits), max(english_hits), min(chinese_hits), max(chinese_hits)))

    anchors.sort()
    if not anchors:
        return [(0, len(english_cues) - 1, 0, len(chinese_sequence) - 1)] if english_cues and chinese_sequence else []

    windows: list[tuple[int, int, int, int]] = []
    prev_eng_end = -1
    prev_zh_end = -1
    for eng_start, eng_end, zh_start, zh_end in anchors:
        win_eng_start = prev_eng_end + 1
        win_eng_end = eng_start - 1
        win_zh_start = prev_zh_end + 1
        win_zh_end = zh_start - 1
        if win_eng_start <= win_eng_end and win_zh_start <= win_zh_end:
            windows.append((win_eng_start, win_eng_end, win_zh_start, win_zh_end))
        prev_eng_end = max(prev_eng_end, eng_end)
        prev_zh_end = max(prev_zh_end, zh_end)

    tail_eng_start = prev_eng_end + 1
    tail_zh_start = prev_zh_end + 1
    if tail_eng_start <= len(english_cues) - 1 and tail_zh_start <= len(chinese_sequence) - 1:
        windows.append((tail_eng_start, len(english_cues) - 1, tail_zh_start, len(chinese_sequence) - 1))

    return windows


def to_group_english_cues(cues: list[FullEnglishCue]) -> list[EnglishCue]:
    outputs: list[EnglishCue] = []
    for index, cue in enumerate(cues):
        outputs.append(
            EnglishCue(
                segment_id=cue.cue_id,
                segment_ids=[cue.cue_id],
                index=index,
                start=cue.start,
                end=cue.end,
                text=cue.text,
                semantic_text=cue.semantic_text,
            )
        )
    return outputs


def to_group_chinese_cues(cues: list[FullChineseCue]) -> list[ChineseCue]:
    outputs: list[ChineseCue] = []
    for index, cue in enumerate(cues):
        outputs.append(
            ChineseCue(
                clip_name=cue.clip_name,
                cue_index=cue.cue_index,
                order_index=index,
                start=cue.start,
                end=cue.end,
                text=cue.text,
                semantic_text=cue.semantic_text,
                confidence=cue.confidence,
            )
        )
    return outputs


def build_base_row(cue: FullEnglishCue) -> dict[str, Any]:
    return {
        "segment_id": cue.cue_id,
        "part_name": cue.part_name,
        "start": cue.start,
        "end": cue.end,
        "duration": round(max(0.0, cue.end - cue.start), 3),
        "english_text": cue.text,
        "english_cue_id": cue.cue_id,
        "status": "unmatched",
        "match_origin": "none",
        "match_score": None,
        "chinese_confidence": None,
        "source_clip": None,
        "chinese_text": "",
        "chinese_cue_ids": [],
        "reviewed_source_segment_id": None,
        "group_english_cue_ids": [cue.cue_id],
        "notes": "",
    }


def reviewed_status(row: dict[str, Any]) -> str:
    english_count = len(row.get("english_cue_ids") or [])
    chinese_count = len(row.get("chinese_cue_ids") or [])
    if english_count > 1:
        return "merged-n1"
    if chinese_count > 1:
        return "merged-1n"
    return "matched-high"


def quality_from_auto(score: float, chinese_confidence: float, args: argparse.Namespace) -> str:
    adjusted = score * (0.8 + (0.2 * max(0.0, min(1.0, chinese_confidence))))
    if adjusted >= args.high_threshold:
        return "matched-high"
    if adjusted >= args.medium_threshold:
        return "matched-medium"
    if adjusted >= args.low_threshold:
        return "matched-low"
    return "unmatched"


def english_word_count(text: str) -> int:
    return len([part for part in re.split(r"\s+", text.strip()) if part])


def cjk_count(text: str) -> int:
    return sum("\u4e00" <= ch <= "\u9fff" for ch in text)


def ascii_alpha_count(text: str) -> int:
    return sum(ch.isascii() and ch.isalpha() for ch in text)


def has_explicit_speaker(text: str) -> bool:
    normalized = normalize_text(text)
    if "：" in normalized:
        prefix = normalized.split("：", 1)[0].strip()
        return 0 < len(prefix) <= 12
    if ":" in normalized:
        prefix = normalized.split(":", 1)[0].strip()
        return 0 < len(prefix) <= 30 and prefix[:1].isalpha()
    return False


def repeated_phrase(text: str) -> bool:
    normalized = re.sub(r"\s+", "", normalize_text(text))
    return bool(normalized and re.search(r"(.{2,})\1\1", normalized))


def is_question_like(text: str) -> bool:
    normalized = normalize_text(text)
    return "?" in normalized or "？" in normalized


def looks_like_stage_direction(text: str) -> bool:
    normalized = normalize_text(text).lower()
    keywords = (
        "laugh",
        "chuckle",
        "sob",
        "cry",
        "wail",
        "grunt",
        "gasp",
        "scream",
        "shiver",
        "snarl",
        "sneer",
        "wince",
        "noise",
        "发抖",
        "啜泣",
        "厌恶声",
        "沮丧声",
        "笑",
        "哭",
        "哀号",
        "呻吟",
    )
    return ("(" in normalized or "（" in normalized) and any(keyword in normalized for keyword in keywords)


def evaluate_generated_match(
    english_text: str,
    chinese_text: str,
    match_origin: str,
    score: float,
) -> list[str]:
    if match_origin in {"none", "reviewed-master"}:
        return []

    english_semantic = prepare_english_text(english_text)
    chinese_semantic = prepare_chinese_text(chinese_text)
    english_words = english_word_count(english_semantic or english_text)
    zh_cjk = cjk_count(chinese_text)
    zh_ascii = ascii_alpha_count(chinese_text)
    english_has_speaker = has_explicit_speaker(english_text)
    chinese_has_speaker = has_explicit_speaker(chinese_text)
    question_pair = is_question_like(english_text) and is_question_like(chinese_text)
    stage_direction_pair = looks_like_stage_direction(english_text) and looks_like_stage_direction(chinese_text)

    reasons: list[str] = []
    if zh_cjk == 0:
        reasons.append("no-cjk")
    if zh_ascii >= 3:
        reasons.append("ascii-noise")
    if repeated_phrase(chinese_text):
        reasons.append("repeated-ocr-fragment")
    if not chinese_semantic and english_words >= 2:
        reasons.append("empty-semantic-after-clean")
    if zh_cjk <= 2 and english_words >= 2 and not (chinese_has_speaker and score >= 0.75):
        reasons.append("too-short-for-english-length")
    if (
        english_has_speaker
        and not chinese_has_speaker
        and zh_cjk <= 4
        and english_words >= 2
        and not (score >= 0.76 and zh_cjk >= 4)
    ):
        reasons.append("speaker-missing-on-short-zh")
    if (
        match_origin.startswith("group-")
        and zh_cjk <= 4
        and english_words >= 2
        and score < 0.75
        and not (chinese_has_speaker and question_pair)
        and not (score >= 0.74 and stage_direction_pair and chinese_has_speaker)
    ):
        reasons.append("short-group-match")
    if (
        match_origin.startswith("group-clip-")
        and english_has_speaker
        and not chinese_has_speaker
        and english_words >= 2
        and score < 0.74
    ):
        reasons.append("clip-local-speaker-mismatch")
    return reasons


def sanitize_generated_row(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    updated = dict(row)
    updated["status"] = "unmatched"
    updated["match_origin"] = "quality-gated-qc1-inline"
    updated["match_score"] = None
    updated["chinese_confidence"] = None
    updated["source_clip"] = None
    updated["chinese_text"] = ""
    updated["chinese_cue_ids"] = []
    updated["notes"] = f"qc1-inline-rejected: {', '.join(reasons)}"
    return updated


def reserve_reviewed_rows(
    reviewed_payload: dict[str, Any],
    rows_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, set[int]], Counter[str]]:
    reserved_chinese: dict[str, set[int]] = defaultdict(set)
    status_counter: Counter[str] = Counter()

    for row in reviewed_payload.get("segments") or []:
        english_ids = [str(item) for item in row.get("english_cue_ids") or []]
        chinese_ids = [int(item) for item in row.get("chinese_cue_ids") or [] if str(item).strip()]
        source_clip = str(row.get("source_clip") or "")
        status = reviewed_status(row)
        for english_id in english_ids:
            target = rows_by_id.get(english_id)
            if target is None:
                continue
            target["status"] = status
            target["match_origin"] = "reviewed-master"
            target["match_score"] = row.get("match_score")
            target["chinese_confidence"] = 1.0
            target["source_clip"] = source_clip or None
            target["chinese_text"] = str(row.get("chinese_text") or "")
            target["chinese_cue_ids"] = [str(item) for item in row.get("chinese_cue_ids") or []]
            target["reviewed_source_segment_id"] = str(row.get("global_segment_id") or "")
            target["group_english_cue_ids"] = english_ids
            target["notes"] = "locked-from-phase-b-reviewed-master"
            status_counter[status] += 1
        if source_clip:
            reserved_chinese[source_clip].update(chinese_ids)

    return reserved_chinese, status_counter


def assign_clip_english_cues(
    english_cues: list[FullEnglishCue],
    clip_assignments: list[dict[str, Any]],
) -> dict[str, list[FullEnglishCue]]:
    assignments: dict[str, list[FullEnglishCue]] = {str(item["clip_name"]): [] for item in clip_assignments}
    ordered = sorted(clip_assignments, key=lambda item: int(item.get("clip_order_in_part") or 0))

    for cue in english_cues:
        chosen_clip: str | None = None
        for offset, clip in enumerate(ordered):
            clip_name = str(clip["clip_name"])
            start = float(clip.get("part_cut_start") or 0.0)
            end = float(clip.get("part_cut_end") or start)
            is_last = offset == len(ordered) - 1
            if cue.midpoint >= start and (cue.midpoint < end or (is_last and cue.midpoint <= end + 0.001)):
                chosen_clip = clip_name
                break
        if chosen_clip is None and ordered:
            chosen_clip = str(ordered[-1]["clip_name"])
        if chosen_clip is not None:
            assignments.setdefault(chosen_clip, []).append(cue)

    return assignments


def auto_match_clip(
    model: SentenceTransformer,
    english_cues: list[FullEnglishCue],
    chinese_cues: list[FullChineseCue],
    args: argparse.Namespace,
    embedding_store: EmbeddingStore | None,
) -> list[tuple[FullEnglishCue, FullChineseCue, float]]:
    english_matchable = [cue for cue in english_cues if cue.semantic_text]
    chinese_matchable = [cue for cue in chinese_cues if cue.semantic_text]
    if not english_matchable or not chinese_matchable:
        return []

    english_base = encode_texts(model, [cue.semantic_text for cue in english_matchable], 256, embedding_store)
    chinese_base = encode_texts(model, [cue.semantic_text for cue in chinese_matchable], 256, embedding_store)
    english_contexts = build_context_texts([cue.semantic_text for cue in english_matchable], args.context_window, 220)
    chinese_contexts = build_context_texts([cue.semantic_text for cue in chinese_matchable], max(1, args.context_window // 2), 180)
    english_ctx = encode_texts(model, english_contexts, 256, embedding_store)
    chinese_ctx = encode_texts(model, chinese_contexts, 256, embedding_store)

    text_similarity = (0.45 * np.matmul(english_base, chinese_base.T)) + (0.55 * np.matmul(english_ctx, chinese_ctx.T))
    progress_similarity = build_progress_similarity(
        english_matchable,
        chinese_matchable,
        clip_start=min((cue.start for cue in english_matchable), default=0.0),
        clip_end=max((cue.end for cue in english_matchable), default=1.0),
    )
    similarity = text_similarity + (0.08 * progress_similarity)
    band_width = max(120, int(len(chinese_matchable) * 0.28))
    matches = monotonic_align(
        similarity=similarity,
        match_threshold=args.match_threshold,
        output_threshold=args.output_threshold,
        skip_english_penalty=args.skip_english_penalty,
        skip_chinese_penalty=args.skip_chinese_penalty,
        band_width=min(max(len(chinese_matchable), 1), band_width),
    )

    outputs: list[tuple[FullEnglishCue, FullChineseCue, float]] = []
    for english_index, chinese_index, score in matches:
        english_cue = english_matchable[english_index]
        chinese_cue = chinese_matchable[chinese_index]
        if not speaker_compatible(english_cue.text, chinese_cue.text):
            continue
        outputs.append((english_cue, chinese_cue, round(float(score), 4)))
    return outputs


def build_progress_similarity(
    english_cues: list[FullEnglishCue],
    chinese_cues: list[FullChineseCue],
    clip_start: float,
    clip_end: float,
) -> np.ndarray:
    english_span = max(clip_end - clip_start, 1.0)
    chinese_span = max(max((cue.end for cue in chinese_cues), default=0.0), 1.0)
    english_progress = np.array(
        [max(0.0, min(1.0, (cue.midpoint - clip_start) / english_span)) for cue in english_cues],
        dtype=np.float32,
    )
    chinese_progress = np.array(
        [max(0.0, min(1.0, (((cue.start + cue.end) * 0.5) / chinese_span))) for cue in chinese_cues],
        dtype=np.float32,
    )
    delta = np.abs(english_progress[:, None] - chinese_progress[None, :])
    return np.clip(1.0 - (delta / 0.16), 0.0, 1.0)


def build_clip_progress_chunks(
    english_scope: list[FullEnglishCue],
    chinese_scope: list[FullChineseCue],
    target_chunk_size: int,
    zh_pad: int = 12,
) -> list[tuple[list[FullEnglishCue], list[FullChineseCue]]]:
    if len(english_scope) <= max(target_chunk_size, 1) or len(chinese_scope) <= 1:
        return []

    outputs: list[tuple[list[FullEnglishCue], list[FullChineseCue]]] = []
    chunk_size = max(target_chunk_size, 1)
    total_en = len(english_scope)
    total_zh = len(chinese_scope)

    for en_start in range(0, total_en, chunk_size):
        en_end = min(total_en, en_start + chunk_size)
        english_chunk = english_scope[en_start:en_end]
        if not english_chunk:
            continue
        start_ratio = en_start / total_en
        end_ratio = en_end / total_en
        zh_start = max(0, int(round(start_ratio * total_zh)) - zh_pad)
        zh_end = min(total_zh, int(round(end_ratio * total_zh)) + zh_pad)
        chinese_chunk = chinese_scope[zh_start:zh_end]
        if not chinese_chunk:
            continue
        outputs.append((english_chunk, chinese_chunk))
    return outputs


def apply_scope_matches(
    rows_by_id: dict[str, dict[str, Any]],
    english_scope: list[FullEnglishCue],
    chinese_scope: list[FullChineseCue],
    auto_used_chinese: set[tuple[str, int]],
    model: SentenceTransformer,
    args: argparse.Namespace,
    embedding_store: EmbeddingStore | None,
    auto_status_counts: Counter[str],
    auto_origin: str,
    group_origin: str,
    enable_group: bool = True,
) -> None:
    if not english_scope or not chinese_scope:
        return

    matches = auto_match_clip(
        model=model,
        english_cues=english_scope,
        chinese_cues=chinese_scope,
        args=args,
        embedding_store=embedding_store,
    )
    for english_cue, chinese_cue, score in matches:
        row = rows_by_id[english_cue.cue_id]
        if row["match_origin"] != "none":
            continue
        status = quality_from_auto(score, chinese_cue.confidence, args)
        if status == "unmatched":
            continue
        row["status"] = status
        row["match_origin"] = auto_origin
        row["match_score"] = score
        row["chinese_confidence"] = chinese_cue.confidence
        row["source_clip"] = chinese_cue.clip_name
        row["chinese_text"] = chinese_cue.text
        row["chinese_cue_ids"] = [str(chinese_cue.cue_index)]
        row["group_english_cue_ids"] = [english_cue.cue_id]
        row["notes"] = f"auto-matched-{auto_origin}"
        auto_status_counts[status] += 1
        auto_used_chinese.add((chinese_cue.clip_name, chinese_cue.cue_index))

    if not enable_group:
        return

    group_english_scope = [
        cue
        for cue in english_scope
        if rows_by_id[cue.cue_id]["match_origin"] == "none" and cue.semantic_text
    ]
    group_chinese_scope = [
        cue
        for cue in chinese_scope
        if (cue.clip_name, cue.cue_index) not in auto_used_chinese and cue.semantic_text
    ]
    if not group_english_scope or not group_chinese_scope:
        return

    group_matches = align_group_window(
        english_cues=to_group_english_cues(group_english_scope),
        chinese_cues=to_group_chinese_cues(group_chinese_scope),
        model=model,
        max_en_group=2,
        max_zh_group=2,
        match_threshold=0.56,
        output_threshold=0.64,
        skip_en_penalty=0.06,
        skip_zh_penalty=0.04,
        embedding_lookup=(lambda texts, batch_size: encode_texts(model, texts, batch_size, embedding_store)),
    )
    for match in group_matches:
        english_ids = [str(item) for item in match.get("english_cue_ids") or []]
        chinese_ids = [str(item) for item in match.get("chinese_cue_ids") or []]
        if not english_ids or not chinese_ids:
            continue
        if any(rows_by_id[english_id]["match_origin"] != "none" for english_id in english_ids if english_id in rows_by_id):
            continue

        matched_chinese_cues = [
            cue
            for cue in group_chinese_scope
            if str(cue.cue_index) in chinese_ids
        ]
        if not matched_chinese_cues:
            continue

        if len(english_ids) > 1:
            status = "merged-n1"
        elif len(chinese_ids) > 1:
            status = "merged-1n"
        else:
            status = "matched-medium"

        source_clip = matched_chinese_cues[0].clip_name
        confidence = round(
            sum(cue.confidence for cue in matched_chinese_cues) / max(len(matched_chinese_cues), 1),
            4,
        )
        score = round(float(match.get("match_score") or 0.0), 4)
        for english_id in english_ids:
            row = rows_by_id.get(english_id)
            if row is None or row["match_origin"] != "none":
                continue
            row["status"] = status
            row["match_origin"] = group_origin
            row["match_score"] = score
            row["chinese_confidence"] = confidence
            row["source_clip"] = source_clip
            row["chinese_text"] = str(match.get("chinese_text") or "")
            row["chinese_cue_ids"] = list(chinese_ids)
            row["group_english_cue_ids"] = list(english_ids)
            row["notes"] = f"group-dp-{match.get('alignment_type')}-{group_origin}"
            auto_status_counts[status] += 1
        for cue in matched_chinese_cues:
            auto_used_chinese.add((cue.clip_name, cue.cue_index))


def fallback_match_clip(
    model: SentenceTransformer,
    english_cues: list[FullEnglishCue],
    chinese_cues: list[FullChineseCue],
    args: argparse.Namespace,
    clip_start: float,
    clip_end: float,
    embedding_store: EmbeddingStore | None,
) -> list[tuple[FullEnglishCue, FullChineseCue, float]]:
    english_remaining = [cue for cue in english_cues if cue.semantic_text]
    chinese_remaining = [cue for cue in chinese_cues if cue.semantic_text]
    if not english_remaining or not chinese_remaining:
        return []

    english_base = encode_texts(model, [cue.semantic_text for cue in english_remaining], 256, embedding_store)
    chinese_base = encode_texts(model, [cue.semantic_text for cue in chinese_remaining], 256, embedding_store)
    english_contexts = build_context_texts([cue.semantic_text for cue in english_remaining], max(1, args.context_window - 1), 220)
    chinese_contexts = build_context_texts([cue.semantic_text for cue in chinese_remaining], 1, 180)
    english_ctx = encode_texts(model, english_contexts, 256, embedding_store)
    chinese_ctx = encode_texts(model, chinese_contexts, 256, embedding_store)

    text_similarity = (0.55 * np.matmul(english_base, chinese_base.T)) + (0.30 * np.matmul(english_ctx, chinese_ctx.T))
    progress_similarity = build_progress_similarity(english_remaining, chinese_remaining, clip_start=clip_start, clip_end=clip_end)
    similarity = text_similarity + (0.15 * progress_similarity)
    matches = monotonic_align(
        similarity=similarity,
        match_threshold=0.26,
        output_threshold=0.42,
        skip_english_penalty=0.014,
        skip_chinese_penalty=0.012,
        band_width=min(max(len(chinese_remaining), 1), max(180, int(len(chinese_remaining) * 0.45))),
    )

    outputs: list[tuple[FullEnglishCue, FullChineseCue, float]] = []
    for english_index, chinese_index, score in matches:
        english_cue = english_remaining[english_index]
        chinese_cue = chinese_remaining[chinese_index]
        if not speaker_compatible(english_cue.text, chinese_cue.text):
            continue
        outputs.append((english_cue, chinese_cue, round(float(score), 4)))
    return outputs


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "segment_id",
        "part_name",
        "start",
        "end",
        "duration",
        "status",
        "match_origin",
        "match_score",
        "chinese_confidence",
        "source_clip",
        "english_cue_id",
        "chinese_cue_ids",
        "english_text",
        "chinese_text",
        "reviewed_source_segment_id",
        "group_english_cue_ids",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "segment_id": row["segment_id"],
                    "part_name": row["part_name"],
                    "start": row["start"],
                    "end": row["end"],
                    "duration": row["duration"],
                    "status": row["status"],
                    "match_origin": row["match_origin"],
                    "match_score": row["match_score"],
                    "chinese_confidence": row["chinese_confidence"],
                    "source_clip": row["source_clip"],
                    "english_cue_id": row["english_cue_id"],
                    "chinese_cue_ids": ",".join(row.get("chinese_cue_ids") or []),
                    "english_text": str(row.get("english_text") or "").replace("\t", " ").replace("\n", " "),
                    "chinese_text": str(row.get("chinese_text") or "").replace("\t", " ").replace("\n", " "),
                    "reviewed_source_segment_id": row["reviewed_source_segment_id"],
                    "group_english_cue_ids": ",".join(row.get("group_english_cue_ids") or []),
                    "notes": row["notes"],
                }
            )


def write_audit_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "part_name",
        "segment_id",
        "old_status",
        "old_match_origin",
        "old_match_score",
        "reasons",
        "english_text",
        "chinese_text",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(path: Path, rows: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        lines.append(str(index))
        lines.append(f"{format_srt_timestamp(float(row['start']))} --> {format_srt_timestamp(float(row['end']))}")
        lines.append(str(row.get("english_text") or ""))
        chinese_text = str(row.get("chinese_text") or "")
        if chinese_text:
            lines.append(chinese_text)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Phase C Fulltrack Rebuild v1",
        "",
        f"- Version: `{manifest['version']}`",
        f"- Mapping JSON: `{manifest['mapping_json']}`",
        f"- English OCR root: `{manifest['english_ocr_root']}`",
        f"- Chinese OCR root: `{manifest['chinese_ocr_root']}`",
        f"- Reviewed anchor source: `{manifest['reviewed_master_json']}`",
        f"- Total English cues: `{manifest['total_english_cues']}`",
        f"- Matched cues: `{manifest['matched_cues']}`",
        f"- Coverage: `{manifest['coverage_ratio']}`",
        "",
        "## Notes",
        "",
        "- This is the first full-track draft for Phase C.",
        "- Phase B reviewed rows are treated as locked anchors and are not re-matched.",
        "- Remaining cues are filled with a broader monotonic auto-alignment pass.",
        "- Output keeps all English cues, including unmatched ones.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    reviewed_payload = json.loads(args.reviewed_master_json.read_text(encoding="utf-8"))
    selected_parts = resolve_selected_parts(list(mapping.get("parts") or []), args.parts)
    model = load_sentence_model(args.model_name, args.offline_model_only)
    embedding_store: EmbeddingStore | None = None
    if not args.disable_embedding_cache:
        cache_path = args.embedding_cache_dir / f"{sanitize_model_name(args.model_name)}.pkl"
        embedding_store = EmbeddingStore.load(cache_path)

    clip_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for clip in mapping.get("clips") or []:
        clip_groups[str(clip["assigned_part"])].append(clip)

    all_rows: list[dict[str, Any]] = []
    part_payloads: list[dict[str, Any]] = []
    reserved_status_counts: Counter[str] = Counter()
    auto_status_counts: Counter[str] = Counter()
    fallback_status_counts: Counter[str] = Counter()
    rejected_auto_counts: Counter[str] = Counter()
    rejected_auto_by_origin: Counter[str] = Counter()
    rejected_audit_rows: list[dict[str, Any]] = []

    for part in selected_parts:
        part_name = str(part["part_name"])
        english_cues = load_full_english_cues(args.english_ocr_root, part_name)
        rows_by_id = {cue.cue_id: build_base_row(cue) for cue in english_cues}

        reserved_chinese, reviewed_counts = reserve_reviewed_rows(reviewed_payload, rows_by_id)
        reserved_status_counts.update(reviewed_counts)

        clip_assignments = sorted(clip_groups.get(part_name, []), key=lambda item: int(item.get("clip_order_in_part") or 0))
        ordered_clip_names = [str(item["clip_name"]) for item in clip_assignments]
        chinese_sequence = [
            cue
            for cue in load_full_chinese_sequence(args.chinese_ocr_root, ordered_clip_names)
            if cue.cue_index not in reserved_chinese.get(cue.clip_name, set())
        ]
        auto_used_chinese: set[tuple[str, int]] = set()
        if not args.disable_clip_local_first and clip_assignments:
            english_by_clip = assign_clip_english_cues(english_cues, clip_assignments)
            for clip in clip_assignments:
                clip_name = str(clip["clip_name"])
                english_scope = [
                    cue
                    for cue in english_by_clip.get(clip_name, [])
                    if rows_by_id[cue.cue_id]["match_origin"] == "none"
                ]
                chinese_scope = [
                    cue
                    for cue in chinese_sequence
                    if cue.clip_name == clip_name and (cue.clip_name, cue.cue_index) not in auto_used_chinese
                ]
                apply_scope_matches(
                    rows_by_id=rows_by_id,
                    english_scope=english_scope,
                    chinese_scope=chinese_scope,
                    auto_used_chinese=auto_used_chinese,
                    model=model,
                    args=args,
                    embedding_store=embedding_store,
                    auto_status_counts=auto_status_counts,
                    auto_origin="auto-clip-local-v1",
                    group_origin="group-clip-local-v1",
                )
        windows = build_anchor_windows(
            reviewed_payload=reviewed_payload,
            part_name=part_name,
            english_cues=english_cues,
            chinese_sequence=chinese_sequence,
        )

        for eng_start, eng_end, zh_start, zh_end in windows:
            english_window = [
                cue
                for cue in english_cues[eng_start : eng_end + 1]
                if rows_by_id[cue.cue_id]["match_origin"] == "none"
            ]
            chinese_window = [
                cue
                for cue in chinese_sequence[zh_start : zh_end + 1]
                if (cue.clip_name, cue.cue_index) not in auto_used_chinese
            ]
            if not english_window or not chinese_window:
                continue

            apply_scope_matches(
                rows_by_id=rows_by_id,
                english_scope=english_window,
                chinese_scope=chinese_window,
                auto_used_chinese=auto_used_chinese,
                model=model,
                args=args,
                embedding_store=embedding_store,
                auto_status_counts=auto_status_counts,
                auto_origin="auto-anchor-window-v1",
                group_origin="group-anchor-window-v1",
            )

        if args.enable_fallback:
            fallback_english = [cue for cue in english_cues if rows_by_id[cue.cue_id]["match_origin"] == "none"]
            fallback_chinese = [
                cue
                for cue in chinese_sequence
                if (cue.clip_name, cue.cue_index) not in auto_used_chinese
            ]
            fallback_matches = fallback_match_clip(
                model=model,
                english_cues=fallback_english,
                chinese_cues=fallback_chinese,
                args=args,
                clip_start=0.0,
                clip_end=max((cue.end for cue in english_cues), default=1.0),
                embedding_store=embedding_store,
            )
            for english_cue, chinese_cue, score in fallback_matches:
                row = rows_by_id[english_cue.cue_id]
                if row["match_origin"] != "none":
                    continue
                row["status"] = "matched-low"
                row["match_origin"] = "progress-fallback-v1"
                row["match_score"] = score
                row["chinese_confidence"] = chinese_cue.confidence
                row["source_clip"] = chinese_cue.clip_name
                row["chinese_text"] = chinese_cue.text
                row["chinese_cue_ids"] = [str(chinese_cue.cue_index)]
                row["group_english_cue_ids"] = [english_cue.cue_id]
                row["notes"] = "fallback-progress-alignment-on-full-part-sequence"
                fallback_status_counts["matched-low"] += 1

        for english_id, row in list(rows_by_id.items()):
            reject_reasons = evaluate_generated_match(
                english_text=str(row.get("english_text") or ""),
                chinese_text=str(row.get("chinese_text") or ""),
                match_origin=str(row.get("match_origin") or ""),
                score=float(row.get("match_score") or 0.0),
            )
            if not reject_reasons:
                continue
            for reason in reject_reasons:
                rejected_auto_counts[reason] += 1
            rejected_auto_by_origin[str(row.get("match_origin") or "")] += 1
            rejected_audit_rows.append(
                {
                    "part_name": row["part_name"],
                    "segment_id": row["segment_id"],
                    "old_status": row["status"],
                    "old_match_origin": row["match_origin"],
                    "old_match_score": row["match_score"],
                    "reasons": ",".join(reject_reasons),
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                }
            )
            rows_by_id[english_id] = sanitize_generated_row(row, reject_reasons)

        part_rows = sorted(rows_by_id.values(), key=lambda item: (float(item["start"]), float(item["end"]), item["segment_id"]))
        status_counts = Counter(str(row["status"]) for row in part_rows)
        matched_count = sum(1 for row in part_rows if str(row["status"]) != "unmatched")
        part_payloads.append(
            {
                "part_name": part_name,
                "short_name": part_short_name(part_name),
                "segment_count": len(part_rows),
                "matched_count": matched_count,
                "coverage_ratio": round(matched_count / max(len(part_rows), 1), 4),
                "status_counts": dict(sorted(status_counts.items())),
                "segments": part_rows,
            }
        )
        all_rows.extend(part_rows)
        print(
            json.dumps(
                {
                    "part_name": part_name,
                    "segment_count": len(part_rows),
                    "matched_count": matched_count,
                    "coverage_ratio": round(matched_count / max(len(part_rows), 1), 4),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    all_rows.sort(key=lambda item: (item["part_name"], float(item["start"]), float(item["end"]), item["segment_id"]))
    total_status_counts = Counter(str(row["status"]) for row in all_rows)
    matched_cues = sum(1 for row in all_rows if str(row["status"]) != "unmatched")
    manifest = {
        "version": "phase_c_fulltrack_rebuild_v1",
        "mapping_json": str(args.mapping_json),
        "english_ocr_root": str(args.english_ocr_root),
        "chinese_ocr_root": str(args.chinese_ocr_root),
        "reviewed_master_json": str(args.reviewed_master_json),
        "selected_parts": [str(part["part_name"]) for part in selected_parts],
        "offline_model_only": bool(args.offline_model_only),
        "embedding_cache_path": str((args.embedding_cache_dir / f"{sanitize_model_name(args.model_name)}.pkl")) if embedding_store is not None else None,
        "total_english_cues": len(all_rows),
        "matched_cues": matched_cues,
        "coverage_ratio": round(matched_cues / max(len(all_rows), 1), 4),
        "status_counts": dict(sorted(total_status_counts.items())),
        "reviewed_anchor_status_counts": dict(sorted(reserved_status_counts.items())),
        "auto_status_counts": dict(sorted(auto_status_counts.items())),
        "fallback_status_counts": dict(sorted(fallback_status_counts.items())),
        "rejected_generated_match_counts": dict(sorted(rejected_auto_counts.items())),
        "rejected_generated_match_by_origin": dict(sorted(rejected_auto_by_origin.items())),
        "rejected_generated_row_count": len(rejected_audit_rows),
        "embedding_cache_stats": (
            {
                "cache_hits": embedding_store.cache_hits,
                "cache_misses": embedding_store.cache_misses,
                "save_count": embedding_store.save_count,
                "stored_texts": len(embedding_store.vectors),
            }
            if embedding_store is not None
            else None
        ),
        "parts": [
            {
                "part_name": payload["part_name"],
                "segment_count": payload["segment_count"],
                "matched_count": payload["matched_count"],
                "coverage_ratio": payload["coverage_ratio"],
                "status_counts": payload["status_counts"],
            }
            for payload in part_payloads
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(
        args.output_dir / "all_segments.json",
        {
            "manifest": manifest,
            "segments": all_rows,
        },
    )
    write_tsv(args.output_dir / "all_segments.tsv", all_rows)
    write_readme(args.output_dir / "README.md", manifest)
    write_audit_tsv(args.output_dir / "inline_qc_rejected_rows.tsv", rejected_audit_rows)
    write_json(args.output_dir / "inline_qc_rejected_rows.json", {"rows": rejected_audit_rows})

    for payload in part_payloads:
        short_name = str(payload["short_name"])
        part_dir = args.output_dir / short_name
        write_json(part_dir / f"{short_name}.draft.json", payload)
        write_tsv(part_dir / f"{short_name}.draft.tsv", list(payload["segments"]))
        write_srt(part_dir / f"{short_name}.draft.srt", list(payload["segments"]))

    if embedding_store is not None:
        embedding_store.save()
        manifest["embedding_cache_stats"] = {
            "cache_hits": embedding_store.cache_hits,
            "cache_misses": embedding_store.cache_misses,
            "save_count": embedding_store.save_count,
            "stored_texts": len(embedding_store.vectors),
        }
        write_json(args.output_dir / "manifest.json", manifest)
        write_json(
            args.output_dir / "all_segments.json",
            {
                "manifest": manifest,
                "segments": all_rows,
            },
        )

    print(f"wrote phase c draft -> {args.output_dir}")


if __name__ == "__main__":
    main()
