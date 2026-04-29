from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from build_phase_b_cue_local_align import align_window as align_group_window
from build_phase_c_fulltrack_rebuild import (
    DEFAULT_CHINESE_OCR_ROOT,
    DEFAULT_EMBEDDING_CACHE_DIR,
    DEFAULT_ENGLISH_OCR_ROOT,
    DEFAULT_MAPPING_JSON,
    DEFAULT_REVIEWED_MASTER_JSON,
    EmbeddingStore,
    FullChineseCue,
    FullEnglishCue,
    assign_clip_english_cues,
    build_context_texts,
    build_clip_progress_chunks,
    build_progress_similarity,
    encode_texts,
    load_full_chinese_cues,
    load_full_english_cues,
    load_sentence_model,
    monotonic_align,
    normalize_text,
    part_short_name,
    resolve_selected_parts,
    sanitize_model_name,
    speaker_compatible,
    to_group_chinese_cues,
    to_group_english_cues,
    write_json,
    write_srt,
    write_tsv,
)


DEFAULT_BASE_JSON = Path("scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2/all_segments.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_english_first_forced_rematch_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggressively rematch unmatched Phase C rows using English cues as the fixed skeleton."
    )
    parser.add_argument("--mapping-json", type=Path, default=DEFAULT_MAPPING_JSON)
    parser.add_argument("--base-json", type=Path, default=DEFAULT_BASE_JSON)
    parser.add_argument("--reviewed-master-json", type=Path, default=DEFAULT_REVIEWED_MASTER_JSON)
    parser.add_argument("--chinese-ocr-root", type=Path, default=DEFAULT_CHINESE_OCR_ROOT)
    parser.add_argument("--english-ocr-root", type=Path, default=DEFAULT_ENGLISH_OCR_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model-name", type=str, default="paraphrase-multilingual-MiniLM-L12-v2")
    parser.add_argument("--parts", nargs="*")
    parser.add_argument("--offline-model-only", action="store_true")
    parser.add_argument("--embedding-cache-dir", type=Path, default=DEFAULT_EMBEDDING_CACHE_DIR)
    parser.add_argument("--disable-embedding-cache", action="store_true")
    parser.add_argument("--context-window", type=int, default=2)
    parser.add_argument("--clip-match-threshold", type=float, default=0.06)
    parser.add_argument("--clip-output-threshold", type=float, default=0.12)
    parser.add_argument("--clip-skip-english-penalty", type=float, default=0.004)
    parser.add_argument("--clip-skip-chinese-penalty", type=float, default=0.002)
    parser.add_argument("--clip-extra-rounds", type=int, default=2)
    parser.add_argument("--chunk-target-size", type=int, default=64)
    parser.add_argument("--gap-rescue-min-run", type=int, default=3)
    parser.add_argument("--group-gap-min-run", type=int, default=2)
    parser.add_argument("--micro-gap-max-run", type=int, default=2)
    parser.add_argument("--micro-gap-max-zh", type=int, default=3)
    parser.add_argument("--tail-fill-min-english", type=int, default=20)
    parser.add_argument("--tail-fill-min-zh-ratio", type=float, default=0.8)
    parser.add_argument("--part-tail-fill-min-english", type=int, default=60)
    parser.add_argument("--part-tail-fill-min-zh-ratio", type=float, default=0.45)
    parser.add_argument("--enable-part-global", action="store_true")
    parser.add_argument("--part-match-threshold", type=float, default=0.04)
    parser.add_argument("--part-output-threshold", type=float, default=0.09)
    parser.add_argument("--part-skip-english-penalty", type=float, default=0.003)
    parser.add_argument("--part-skip-chinese-penalty", type=float, default=0.0015)
    return parser.parse_args()


def semantic_en(cue: FullEnglishCue) -> str:
    return cue.semantic_text or normalize_text(cue.text)


def semantic_zh(cue: FullChineseCue) -> str:
    return cue.semantic_text or normalize_text(cue.text)


def has_explicit_speaker(text: str) -> bool:
    normalized = normalize_text(text)
    if "：" in normalized:
        prefix = normalized.split("：", 1)[0].strip()
        return 0 < len(prefix) <= 12
    if ":" in normalized:
        prefix = normalized.split(":", 1)[0].strip()
        return 0 < len(prefix) <= 30 and prefix[:1].isalpha()
    return False


def english_char_count(text: str) -> int:
    normalized = normalize_text(text)
    return sum(1 for ch in normalized if ch.isascii() and (ch.isalpha() or ch.isdigit()))


def chinese_char_count(text: str) -> int:
    normalized = normalize_text(text)
    return sum("\u4e00" <= ch <= "\u9fff" for ch in normalized)


def estimate_status(score: float) -> str:
    if score >= 0.70:
        return "matched-high"
    if score >= 0.42:
        return "matched-medium"
    return "matched-low"


def build_clip_anchor_windows(
    clip_name: str,
    clip_english: list[FullEnglishCue],
    clip_chinese: list[FullChineseCue],
    rows_by_id: dict[str, dict[str, Any]],
) -> list[tuple[int, int, int, int]]:
    english_pos = {cue.cue_id: index for index, cue in enumerate(clip_english)}
    chinese_pos = {cue.cue_index: index for index, cue in enumerate(clip_chinese)}

    anchors: list[tuple[int, int, int, int]] = []
    for cue in clip_english:
        row = rows_by_id.get(cue.cue_id) or {}
        if str(row.get("status") or "") == "unmatched":
            continue
        if str(row.get("source_clip") or "") != clip_name:
            continue
        chinese_ids = [int(item) for item in row.get("chinese_cue_ids") or [] if str(item).strip().isdigit()]
        if not chinese_ids:
            continue
        english_index = english_pos[cue.cue_id]
        chinese_hits = [chinese_pos[item] for item in chinese_ids if item in chinese_pos]
        if not chinese_hits:
            continue
        anchors.append((english_index, english_index, min(chinese_hits), max(chinese_hits)))

    anchors.sort()
    if not anchors:
        return [(0, len(clip_english) - 1, 0, len(clip_chinese) - 1)] if clip_english and clip_chinese else []

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
    if tail_eng_start <= len(clip_english) - 1 and tail_zh_start <= len(clip_chinese) - 1:
        windows.append((tail_eng_start, len(clip_english) - 1, tail_zh_start, len(clip_chinese) - 1))
    return windows


def similarity_with_penalties(
    english_cues: list[FullEnglishCue],
    chinese_cues: list[FullChineseCue],
    model: Any,
    embedding_store: EmbeddingStore | None,
    context_window: int,
    clip_start: float,
    clip_end: float,
    progress_weight: float,
) -> np.ndarray:
    english_texts = [semantic_en(cue) for cue in english_cues]
    chinese_texts = [semantic_zh(cue) for cue in chinese_cues]
    english_base = encode_texts(model, english_texts, 256, embedding_store)
    chinese_base = encode_texts(model, chinese_texts, 256, embedding_store)
    english_contexts = build_context_texts(english_texts, context_window, 240)
    chinese_contexts = build_context_texts(chinese_texts, max(1, context_window // 2), 180)
    english_ctx = encode_texts(model, english_contexts, 256, embedding_store)
    chinese_ctx = encode_texts(model, chinese_contexts, 256, embedding_store)

    text_similarity = (0.76 * np.matmul(english_base, chinese_base.T)) + (0.24 * np.matmul(english_ctx, chinese_ctx.T))
    progress_similarity = build_progress_similarity(
        english_cues,
        chinese_cues,
        clip_start=clip_start,
        clip_end=clip_end,
    )
    similarity = text_similarity + (progress_weight * progress_similarity)

    for en_index, english_cue in enumerate(english_cues):
        english_has_speaker = has_explicit_speaker(english_cue.text)
        en_chars = english_char_count(english_cue.text)
        for zh_index, chinese_cue in enumerate(chinese_cues):
            zh_text = chinese_cue.text
            zh_has_speaker = has_explicit_speaker(zh_text)
            zh_chars = chinese_char_count(zh_text)
            if not speaker_compatible(english_cue.text, zh_text):
                similarity[en_index, zh_index] -= 0.06
            if english_has_speaker and not zh_has_speaker:
                similarity[en_index, zh_index] -= 0.04
            if zh_chars <= 1 and en_chars >= 6:
                similarity[en_index, zh_index] -= 0.08
            elif zh_chars <= 2 and en_chars >= 10:
                similarity[en_index, zh_index] -= 0.05
    return similarity


def aggressive_match_scope(
    english_cues: list[FullEnglishCue],
    chinese_cues: list[FullChineseCue],
    model: Any,
    embedding_store: EmbeddingStore | None,
    context_window: int,
    clip_start: float,
    clip_end: float,
    match_threshold: float,
    output_threshold: float,
    skip_english_penalty: float,
    skip_chinese_penalty: float,
    progress_weight: float,
    band_ratio: float,
) -> list[tuple[FullEnglishCue, FullChineseCue, float]]:
    english_scope = [cue for cue in english_cues if semantic_en(cue)]
    chinese_scope = [cue for cue in chinese_cues if semantic_zh(cue)]
    if not english_scope or not chinese_scope:
        return []

    similarity = similarity_with_penalties(
        english_cues=english_scope,
        chinese_cues=chinese_scope,
        model=model,
        embedding_store=embedding_store,
        context_window=context_window,
        clip_start=clip_start,
        clip_end=clip_end,
        progress_weight=progress_weight,
    )
    band_width = max(80, int(len(chinese_scope) * band_ratio))
    matches = monotonic_align(
        similarity=similarity,
        match_threshold=match_threshold,
        output_threshold=output_threshold,
        skip_english_penalty=skip_english_penalty,
        skip_chinese_penalty=skip_chinese_penalty,
        band_width=min(max(len(chinese_scope), 1), band_width),
    )

    outputs: list[tuple[FullEnglishCue, FullChineseCue, float]] = []
    for english_index, chinese_index, score in matches:
        outputs.append((english_scope[english_index], chinese_scope[chinese_index], round(float(score), 4)))
    return outputs


def apply_matches(
    rows_by_id: dict[str, dict[str, Any]],
    matches: list[tuple[FullEnglishCue, FullChineseCue, float]],
    used_chinese: set[tuple[str, int]],
    origin: str,
    origin_counter: Counter[str],
) -> int:
    applied = 0
    for english_cue, chinese_cue, score in matches:
        row = rows_by_id.get(english_cue.cue_id)
        if row is None or str(row.get("status") or "") != "unmatched":
            continue
        key = (chinese_cue.clip_name, chinese_cue.cue_index)
        if key in used_chinese:
            continue
        row["status"] = estimate_status(score)
        row["match_origin"] = origin
        row["match_score"] = score
        row["chinese_confidence"] = chinese_cue.confidence
        row["source_clip"] = chinese_cue.clip_name
        row["chinese_text"] = chinese_cue.text
        row["chinese_cue_ids"] = [str(chinese_cue.cue_index)]
        row["group_english_cue_ids"] = [english_cue.cue_id]
        row["notes"] = f"forced-english-first-{origin}"
        used_chinese.add(key)
        origin_counter[origin] += 1
        applied += 1
    return applied


def run_clip_window_pass(
    clip_name: str,
    clip_english: list[FullEnglishCue],
    clip_chinese: list[FullChineseCue],
    rows_by_id: dict[str, dict[str, Any]],
    used_chinese: set[tuple[str, int]],
    model: Any,
    embedding_store: EmbeddingStore | None,
    context_window: int,
    match_threshold: float,
    output_threshold: float,
    skip_english_penalty: float,
    skip_chinese_penalty: float,
    progress_weight: float,
    origin_counter: Counter[str],
    origin_name: str,
    chunk_target_size: int,
) -> int:
    applied_total = 0
    windows = build_clip_anchor_windows(
        clip_name=clip_name,
        clip_english=clip_english,
        clip_chinese=clip_chinese,
        rows_by_id=rows_by_id,
    )
    for eng_start, eng_end, zh_start, zh_end in windows:
        english_scope = [
            cue
            for cue in clip_english[eng_start : eng_end + 1]
            if str(rows_by_id[cue.cue_id].get("status") or "") == "unmatched"
        ]
        chinese_scope = [
            cue
            for cue in clip_chinese[zh_start : zh_end + 1]
            if (cue.clip_name, cue.cue_index) not in used_chinese
        ]
        if not english_scope or not chinese_scope:
            continue
        chunk_pairs = build_clip_progress_chunks(english_scope, chinese_scope, target_chunk_size=chunk_target_size)
        if chunk_pairs:
            for english_chunk, chinese_chunk in chunk_pairs:
                english_chunk = [
                    cue for cue in english_chunk if str(rows_by_id[cue.cue_id].get("status") or "") == "unmatched"
                ]
                chinese_chunk = [
                    cue for cue in chinese_chunk if (cue.clip_name, cue.cue_index) not in used_chinese
                ]
                if not english_chunk or not chinese_chunk:
                    continue
                matches = aggressive_match_scope(
                    english_cues=english_chunk,
                    chinese_cues=chinese_chunk,
                    model=model,
                    embedding_store=embedding_store,
                    context_window=context_window,
                    clip_start=min((cue.start for cue in english_chunk), default=0.0),
                    clip_end=max((cue.end for cue in english_chunk), default=1.0),
                    match_threshold=match_threshold,
                    output_threshold=output_threshold,
                    skip_english_penalty=skip_english_penalty,
                    skip_chinese_penalty=skip_chinese_penalty,
                    progress_weight=progress_weight,
                    band_ratio=1.0,
                )
                applied_total += apply_matches(
                    rows_by_id=rows_by_id,
                    matches=matches,
                    used_chinese=used_chinese,
                    origin=origin_name,
                    origin_counter=origin_counter,
                )
        else:
            matches = aggressive_match_scope(
                english_cues=english_scope,
                chinese_cues=chinese_scope,
                model=model,
                embedding_store=embedding_store,
                context_window=context_window,
                clip_start=min((cue.start for cue in english_scope), default=0.0),
                clip_end=max((cue.end for cue in english_scope), default=1.0),
                match_threshold=match_threshold,
                output_threshold=output_threshold,
                skip_english_penalty=skip_english_penalty,
                skip_chinese_penalty=skip_chinese_penalty,
                progress_weight=progress_weight,
                band_ratio=1.0,
            )
            applied_total += apply_matches(
                rows_by_id=rows_by_id,
                matches=matches,
                used_chinese=used_chinese,
                origin=origin_name,
                origin_counter=origin_counter,
            )
    return applied_total


def nearest_matched_chinese_bounds(
    clip_english: list[FullEnglishCue],
    rows_by_id: dict[str, dict[str, Any]],
    run_start: int,
    run_end: int,
) -> tuple[int | None, int | None]:
    prev_zh: int | None = None
    next_zh: int | None = None

    for index in range(run_start - 1, -1, -1):
        row = rows_by_id.get(clip_english[index].cue_id) or {}
        ids = [int(item) for item in row.get("chinese_cue_ids") or [] if str(item).strip().isdigit()]
        if ids:
            prev_zh = max(ids)
            break

    for index in range(run_end + 1, len(clip_english)):
        row = rows_by_id.get(clip_english[index].cue_id) or {}
        ids = [int(item) for item in row.get("chinese_cue_ids") or [] if str(item).strip().isdigit()]
        if ids:
            next_zh = min(ids)
            break

    return prev_zh, next_zh


def run_clip_gap_rescue(
    clip_name: str,
    clip_english: list[FullEnglishCue],
    clip_chinese: list[FullChineseCue],
    rows_by_id: dict[str, dict[str, Any]],
    used_chinese: set[tuple[str, int]],
    model: Any,
    embedding_store: EmbeddingStore | None,
    context_window: int,
    min_run: int,
    chunk_target_size: int,
    origin_counter: Counter[str],
) -> int:
    chinese_pos = {cue.cue_index: idx for idx, cue in enumerate(clip_chinese)}
    applied_total = 0
    total_en = len(clip_english)
    total_zh = len(clip_chinese)
    if total_en <= 0 or total_zh <= 0:
        return 0

    index = 0
    while index < total_en:
        cue = clip_english[index]
        if str(rows_by_id[cue.cue_id].get("status") or "") != "unmatched":
            index += 1
            continue
        run_start = index
        while index + 1 < total_en and str(rows_by_id[clip_english[index + 1].cue_id].get("status") or "") == "unmatched":
            index += 1
        run_end = index
        run_len = run_end - run_start + 1
        index += 1

        if run_len < min_run:
            continue

        prev_zh_id, next_zh_id = nearest_matched_chinese_bounds(clip_english, rows_by_id, run_start, run_end)
        if prev_zh_id is not None and prev_zh_id in chinese_pos:
            zh_start = chinese_pos[prev_zh_id] + 1
        else:
            zh_start = max(0, int(round((run_start / total_en) * total_zh)) - 10)
        if next_zh_id is not None and next_zh_id in chinese_pos:
            zh_end = chinese_pos[next_zh_id] - 1
        else:
            zh_end = min(total_zh - 1, int(round(((run_end + 1) / total_en) * total_zh)) + 10)

        if zh_start > zh_end:
            zh_start = max(0, min(zh_start, total_zh - 1))
            zh_end = min(total_zh - 1, max(zh_start, zh_end))

        english_scope = [
            cue
            for cue in clip_english[run_start : run_end + 1]
            if str(rows_by_id[cue.cue_id].get("status") or "") == "unmatched"
        ]
        chinese_scope = [
            cue
            for cue in clip_chinese[zh_start : zh_end + 1]
            if (cue.clip_name, cue.cue_index) not in used_chinese
        ]
        if not english_scope or not chinese_scope:
            continue

        chunk_pairs = build_clip_progress_chunks(
            english_scope,
            chinese_scope,
            target_chunk_size=max(12, chunk_target_size // 2),
        )
        if not chunk_pairs:
            chunk_pairs = [(english_scope, chinese_scope)]

        for english_chunk, chinese_chunk in chunk_pairs:
            english_chunk = [
                cue for cue in english_chunk if str(rows_by_id[cue.cue_id].get("status") or "") == "unmatched"
            ]
            chinese_chunk = [
                cue for cue in chinese_chunk if (cue.clip_name, cue.cue_index) not in used_chinese
            ]
            if not english_chunk or not chinese_chunk:
                continue
            matches = aggressive_match_scope(
                english_cues=english_chunk,
                chinese_cues=chinese_chunk,
                model=model,
                embedding_store=embedding_store,
                context_window=max(1, context_window - 1),
                clip_start=min((cue.start for cue in english_chunk), default=0.0),
                clip_end=max((cue.end for cue in english_chunk), default=1.0),
                match_threshold=0.02,
                output_threshold=0.06,
                skip_english_penalty=0.002,
                skip_chinese_penalty=0.001,
                progress_weight=0.36,
                band_ratio=1.0,
            )
            applied_total += apply_matches(
                rows_by_id=rows_by_id,
                matches=matches,
                used_chinese=used_chinese,
                origin="forced-gap-rescue-v1",
                origin_counter=origin_counter,
            )
    return applied_total


def apply_group_matches(
    rows_by_id: dict[str, dict[str, Any]],
    english_scope: list[FullEnglishCue],
    chinese_scope: list[FullChineseCue],
    used_chinese: set[tuple[str, int]],
    model: Any,
    embedding_store: EmbeddingStore | None,
    origin_counter: Counter[str],
    origin_name: str,
) -> int:
    group_english = [cue for cue in english_scope if str(rows_by_id[cue.cue_id].get("status") or "") == "unmatched" and semantic_en(cue)]
    group_chinese = [cue for cue in chinese_scope if (cue.clip_name, cue.cue_index) not in used_chinese and semantic_zh(cue)]
    if not group_english or not group_chinese:
        return 0

    matches = align_group_window(
        english_cues=to_group_english_cues(group_english),
        chinese_cues=to_group_chinese_cues(group_chinese),
        model=model,
        max_en_group=2,
        max_zh_group=2,
        match_threshold=0.30,
        output_threshold=0.38,
        skip_en_penalty=0.015,
        skip_zh_penalty=0.01,
        embedding_lookup=(lambda texts, batch_size: encode_texts(model, texts, batch_size, embedding_store)),
    )

    applied = 0
    for match in matches:
        english_ids = [str(item) for item in match.get("english_cue_ids") or []]
        chinese_ids = [str(item) for item in match.get("chinese_cue_ids") or []]
        if not english_ids or not chinese_ids:
            continue
        if any(str(rows_by_id.get(english_id, {}).get("status") or "") != "unmatched" for english_id in english_ids):
            continue

        matched_chinese_cues = [cue for cue in group_chinese if str(cue.cue_index) in chinese_ids]
        if not matched_chinese_cues:
            continue

        if len(english_ids) > 1:
            status = "merged-n1"
        elif len(chinese_ids) > 1:
            status = "merged-1n"
        else:
            score = float(match.get("match_score") or 0.0)
            status = estimate_status(score)

        source_clip = matched_chinese_cues[0].clip_name
        confidence = round(sum(cue.confidence for cue in matched_chinese_cues) / max(len(matched_chinese_cues), 1), 4)
        score = round(float(match.get("match_score") or 0.0), 4)
        for english_id in english_ids:
            row = rows_by_id.get(english_id)
            if row is None or str(row.get("status") or "") != "unmatched":
                continue
            row["status"] = status
            row["match_origin"] = origin_name
            row["match_score"] = score
            row["chinese_confidence"] = confidence
            row["source_clip"] = source_clip
            row["chinese_text"] = str(match.get("chinese_text") or "")
            row["chinese_cue_ids"] = list(chinese_ids)
            row["group_english_cue_ids"] = list(english_ids)
            row["notes"] = f"forced-group-gap-{match.get('alignment_type')}"
            applied += 1
        for cue in matched_chinese_cues:
            used_chinese.add((cue.clip_name, cue.cue_index))
        origin_counter[origin_name] += 1
    return applied


def run_clip_group_gap_rescue(
    clip_name: str,
    clip_english: list[FullEnglishCue],
    clip_chinese: list[FullChineseCue],
    rows_by_id: dict[str, dict[str, Any]],
    used_chinese: set[tuple[str, int]],
    model: Any,
    embedding_store: EmbeddingStore | None,
    min_run: int,
    origin_counter: Counter[str],
) -> int:
    chinese_pos = {cue.cue_index: idx for idx, cue in enumerate(clip_chinese)}
    applied_total = 0
    total_en = len(clip_english)
    total_zh = len(clip_chinese)
    if total_en <= 0 or total_zh <= 0:
        return 0

    index = 0
    while index < total_en:
        if str(rows_by_id[clip_english[index].cue_id].get("status") or "") != "unmatched":
            index += 1
            continue
        run_start = index
        while index + 1 < total_en and str(rows_by_id[clip_english[index + 1].cue_id].get("status") or "") == "unmatched":
            index += 1
        run_end = index
        run_len = run_end - run_start + 1
        index += 1
        if run_len < min_run:
            continue

        prev_zh_id, next_zh_id = nearest_matched_chinese_bounds(clip_english, rows_by_id, run_start, run_end)
        if prev_zh_id is not None and prev_zh_id in chinese_pos:
            zh_start = chinese_pos[prev_zh_id] + 1
        else:
            zh_start = max(0, int(round((run_start / total_en) * total_zh)) - 8)
        if next_zh_id is not None and next_zh_id in chinese_pos:
            zh_end = chinese_pos[next_zh_id] - 1
        else:
            zh_end = min(total_zh - 1, int(round(((run_end + 1) / total_en) * total_zh)) + 8)
        if zh_start > zh_end:
            continue

        english_scope = clip_english[run_start : run_end + 1]
        chinese_scope = [cue for cue in clip_chinese[zh_start : zh_end + 1] if (cue.clip_name, cue.cue_index) not in used_chinese]
        if not english_scope or not chinese_scope:
            continue
        applied_total += apply_group_matches(
            rows_by_id=rows_by_id,
            english_scope=english_scope,
            chinese_scope=chinese_scope,
            used_chinese=used_chinese,
            model=model,
            embedding_store=embedding_store,
            origin_counter=origin_counter,
            origin_name="forced-group-gap-v1",
        )
    return applied_total


def run_clip_micro_gap_fill(
    clip_name: str,
    clip_english: list[FullEnglishCue],
    clip_chinese: list[FullChineseCue],
    rows_by_id: dict[str, dict[str, Any]],
    used_chinese: set[tuple[str, int]],
    max_run: int,
    max_zh: int,
    origin_counter: Counter[str],
) -> int:
    chinese_pos = {cue.cue_index: idx for idx, cue in enumerate(clip_chinese)}
    applied = 0
    index = 0
    while index < len(clip_english):
        if str(rows_by_id[clip_english[index].cue_id].get("status") or "") != "unmatched":
            index += 1
            continue
        run_start = index
        while index + 1 < len(clip_english) and str(rows_by_id[clip_english[index + 1].cue_id].get("status") or "") == "unmatched":
            index += 1
        run_end = index
        run_len = run_end - run_start + 1
        index += 1
        if run_len > max_run:
            continue

        prev_zh_id, next_zh_id = nearest_matched_chinese_bounds(clip_english, rows_by_id, run_start, run_end)
        if prev_zh_id is None or next_zh_id is None:
            continue
        if prev_zh_id not in chinese_pos or next_zh_id not in chinese_pos:
            continue
        zh_start = chinese_pos[prev_zh_id] + 1
        zh_end = chinese_pos[next_zh_id] - 1
        zh_count = zh_end - zh_start + 1
        if zh_count <= 0 or zh_count > max_zh:
            continue

        english_scope = clip_english[run_start : run_end + 1]
        chinese_scope = [
            cue
            for cue in clip_chinese[zh_start : zh_end + 1]
            if (cue.clip_name, cue.cue_index) not in used_chinese
        ]
        if not english_scope or not chinese_scope:
            continue

        pair_count = min(len(english_scope), len(chinese_scope))
        for offset in range(pair_count):
            english_cue = english_scope[offset]
            chinese_cue = chinese_scope[offset]
            row = rows_by_id.get(english_cue.cue_id)
            if row is None or str(row.get("status") or "") != "unmatched":
                continue
            row["status"] = "matched-low"
            row["match_origin"] = "forced-micro-gap-v1"
            row["match_score"] = 0.22
            row["chinese_confidence"] = chinese_cue.confidence
            row["source_clip"] = clip_name
            row["chinese_text"] = chinese_cue.text
            row["chinese_cue_ids"] = [str(chinese_cue.cue_index)]
            row["group_english_cue_ids"] = [english_cue.cue_id]
            row["notes"] = "forced-micro-gap-sequential-fill"
            used_chinese.add((chinese_cue.clip_name, chinese_cue.cue_index))
            applied += 1
        if applied:
            origin_counter["forced-micro-gap-v1"] += 1
    return applied


def spaced_indices(total: int, count: int) -> list[int]:
    if total <= 0 or count <= 0:
        return []
    if count >= total:
        return list(range(total))
    if count == 1:
        return [0]
    seen: list[int] = []
    used: set[int] = set()
    for idx in range(count):
        pos = int(round(idx * (total - 1) / (count - 1)))
        if pos in used:
            continue
        used.add(pos)
        seen.append(pos)
    candidate = 0
    while len(seen) < count and candidate < total:
        if candidate not in used:
            used.add(candidate)
            seen.append(candidate)
        candidate += 1
    seen.sort()
    return seen


def run_clip_tail_fill(
    clip_name: str,
    clip_english: list[FullEnglishCue],
    clip_chinese: list[FullChineseCue],
    rows_by_id: dict[str, dict[str, Any]],
    used_chinese: set[tuple[str, int]],
    min_english: int,
    min_zh_ratio: float,
    origin_counter: Counter[str],
) -> int:
    remaining_english = [cue for cue in clip_english if str(rows_by_id[cue.cue_id].get("status") or "") == "unmatched"]
    remaining_chinese = [cue for cue in clip_chinese if (cue.clip_name, cue.cue_index) not in used_chinese]
    if len(remaining_english) < min_english or not remaining_chinese:
        return 0

    ratio = len(remaining_chinese) / max(len(remaining_english), 1)
    if ratio < min_zh_ratio:
        return 0

    pair_count = min(len(remaining_english), len(remaining_chinese))
    en_indices = spaced_indices(len(remaining_english), pair_count)
    zh_indices = spaced_indices(len(remaining_chinese), pair_count)
    applied = 0
    for en_idx, zh_idx in zip(en_indices, zh_indices):
        english_cue = remaining_english[en_idx]
        chinese_cue = remaining_chinese[zh_idx]
        row = rows_by_id.get(english_cue.cue_id)
        if row is None or str(row.get("status") or "") != "unmatched":
            continue
        row["status"] = "matched-low"
        row["match_origin"] = "forced-tail-fill-v1"
        row["match_score"] = 0.18
        row["chinese_confidence"] = chinese_cue.confidence
        row["source_clip"] = clip_name
        row["chinese_text"] = chinese_cue.text
        row["chinese_cue_ids"] = [str(chinese_cue.cue_index)]
        row["group_english_cue_ids"] = [english_cue.cue_id]
        row["notes"] = "forced-tail-fill-progressive"
        used_chinese.add((chinese_cue.clip_name, chinese_cue.cue_index))
        applied += 1
    if applied:
        origin_counter["forced-tail-fill-v1"] += applied
    return applied


def run_part_tail_fill(
    english_cues: list[FullEnglishCue],
    chinese_sequence: list[FullChineseCue],
    rows_by_id: dict[str, dict[str, Any]],
    used_chinese: set[tuple[str, int]],
    min_english: int,
    min_zh_ratio: float,
    origin_counter: Counter[str],
) -> int:
    remaining_english = [cue for cue in english_cues if str(rows_by_id[cue.cue_id].get("status") or "") == "unmatched"]
    remaining_chinese = [cue for cue in chinese_sequence if (cue.clip_name, cue.cue_index) not in used_chinese]
    if len(remaining_english) < min_english or not remaining_chinese:
        return 0

    ratio = len(remaining_chinese) / max(len(remaining_english), 1)
    if ratio < min_zh_ratio:
        return 0

    pair_count = min(len(remaining_english), len(remaining_chinese))
    en_indices = spaced_indices(len(remaining_english), pair_count)
    zh_indices = spaced_indices(len(remaining_chinese), pair_count)
    applied = 0
    for en_idx, zh_idx in zip(en_indices, zh_indices):
        english_cue = remaining_english[en_idx]
        chinese_cue = remaining_chinese[zh_idx]
        row = rows_by_id.get(english_cue.cue_id)
        if row is None or str(row.get("status") or "") != "unmatched":
            continue
        row["status"] = "matched-low"
        row["match_origin"] = "forced-part-tail-fill-v1"
        row["match_score"] = 0.14
        row["chinese_confidence"] = chinese_cue.confidence
        row["source_clip"] = chinese_cue.clip_name
        row["chinese_text"] = chinese_cue.text
        row["chinese_cue_ids"] = [str(chinese_cue.cue_index)]
        row["group_english_cue_ids"] = [english_cue.cue_id]
        row["notes"] = "forced-part-tail-fill-progressive"
        used_chinese.add((chinese_cue.clip_name, chinese_cue.cue_index))
        applied += 1
    if applied:
        origin_counter["forced-part-tail-fill-v1"] += applied
    return applied


def clone_row(base_row: dict[str, Any], cue: FullEnglishCue) -> dict[str, Any]:
    row = dict(base_row)
    row["segment_id"] = cue.cue_id
    row["part_name"] = cue.part_name
    row["start"] = cue.start
    row["end"] = cue.end
    row["duration"] = round(max(0.0, cue.end - cue.start), 3)
    row["english_text"] = cue.text
    row["english_cue_id"] = cue.cue_id
    row.setdefault("status", "unmatched")
    row.setdefault("match_origin", "none")
    row.setdefault("match_score", None)
    row.setdefault("chinese_confidence", None)
    row.setdefault("source_clip", None)
    row.setdefault("chinese_text", "")
    row.setdefault("chinese_cue_ids", [])
    row.setdefault("reviewed_source_segment_id", None)
    row.setdefault("group_english_cue_ids", [cue.cue_id])
    row.setdefault("notes", "")
    return row


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    base_payload = json.loads(args.base_json.read_text(encoding="utf-8"))
    selected_parts = resolve_selected_parts(list(mapping.get("parts") or []), args.parts)
    base_rows_by_id = {str(row["segment_id"]): dict(row) for row in base_payload.get("segments") or []}

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
    forced_origin_counts: Counter[str] = Counter()

    for part in selected_parts:
        part_name = str(part["part_name"])
        english_cues = load_full_english_cues(args.english_ocr_root, part_name)
        rows_by_id = {
            cue.cue_id: clone_row(base_rows_by_id.get(cue.cue_id) or {}, cue)
            for cue in english_cues
        }

        used_chinese: set[tuple[str, int]] = set()
        for row in rows_by_id.values():
            if str(row.get("status") or "") == "unmatched":
                continue
            source_clip = str(row.get("source_clip") or "")
            if not source_clip:
                continue
            for cue_id in row.get("chinese_cue_ids") or []:
                text = str(cue_id).strip()
                if text.isdigit():
                    used_chinese.add((source_clip, int(text)))

        clip_assignments = sorted(clip_groups.get(part_name, []), key=lambda item: int(item.get("clip_order_in_part") or 0))
        english_by_clip = assign_clip_english_cues(english_cues, clip_assignments)

        for clip in clip_assignments:
            clip_name = str(clip["clip_name"])
            clip_english = list(english_by_clip.get(clip_name, []))
            if not clip_english:
                continue
            clip_chinese = [
                cue
                for cue in load_full_chinese_cues(args.chinese_ocr_root, clip_name)
            ]
            run_clip_window_pass(
                clip_name=clip_name,
                clip_english=clip_english,
                clip_chinese=clip_chinese,
                rows_by_id=rows_by_id,
                used_chinese=used_chinese,
                model=model,
                embedding_store=embedding_store,
                context_window=args.context_window,
                match_threshold=args.clip_match_threshold,
                output_threshold=args.clip_output_threshold,
                skip_english_penalty=args.clip_skip_english_penalty,
                skip_chinese_penalty=args.clip_skip_chinese_penalty,
                progress_weight=0.28,
                origin_counter=forced_origin_counts,
                origin_name="forced-clip-window-v1",
                chunk_target_size=args.chunk_target_size,
            )
            for _ in range(max(args.clip_extra_rounds, 0)):
                applied = run_clip_window_pass(
                    clip_name=clip_name,
                    clip_english=clip_english,
                    clip_chinese=clip_chinese,
                    rows_by_id=rows_by_id,
                    used_chinese=used_chinese,
                    model=model,
                    embedding_store=embedding_store,
                    context_window=max(1, args.context_window - 1),
                    match_threshold=max(0.0, args.clip_match_threshold - 0.02),
                    output_threshold=max(0.0, args.clip_output_threshold - 0.02),
                    skip_english_penalty=max(0.0, args.clip_skip_english_penalty - 0.001),
                    skip_chinese_penalty=max(0.0, args.clip_skip_chinese_penalty - 0.0005),
                    progress_weight=0.32,
                    origin_counter=forced_origin_counts,
                    origin_name="forced-clip-window-rerun-v1",
                    chunk_target_size=max(24, args.chunk_target_size // 2),
                )
                if applied <= 0:
                    break
            run_clip_gap_rescue(
                clip_name=clip_name,
                clip_english=clip_english,
                clip_chinese=clip_chinese,
                rows_by_id=rows_by_id,
                used_chinese=used_chinese,
                model=model,
                embedding_store=embedding_store,
                context_window=args.context_window,
                min_run=args.gap_rescue_min_run,
                chunk_target_size=args.chunk_target_size,
                origin_counter=forced_origin_counts,
            )
            run_clip_group_gap_rescue(
                clip_name=clip_name,
                clip_english=clip_english,
                clip_chinese=clip_chinese,
                rows_by_id=rows_by_id,
                used_chinese=used_chinese,
                model=model,
                embedding_store=embedding_store,
                min_run=args.group_gap_min_run,
                origin_counter=forced_origin_counts,
            )
            run_clip_micro_gap_fill(
                clip_name=clip_name,
                clip_english=clip_english,
                clip_chinese=clip_chinese,
                rows_by_id=rows_by_id,
                used_chinese=used_chinese,
                max_run=args.micro_gap_max_run,
                max_zh=args.micro_gap_max_zh,
                origin_counter=forced_origin_counts,
            )
            run_clip_tail_fill(
                clip_name=clip_name,
                clip_english=clip_english,
                clip_chinese=clip_chinese,
                rows_by_id=rows_by_id,
                used_chinese=used_chinese,
                min_english=args.tail_fill_min_english,
                min_zh_ratio=args.tail_fill_min_zh_ratio,
                origin_counter=forced_origin_counts,
            )

        remaining_english = [cue for cue in english_cues if str(rows_by_id[cue.cue_id].get("status") or "") == "unmatched"]
        chinese_sequence: list[FullChineseCue] = []
        for clip in clip_assignments:
            clip_name = str(clip["clip_name"])
            chinese_sequence.extend(
                cue
                for cue in load_full_chinese_cues(args.chinese_ocr_root, clip_name)
                if (cue.clip_name, cue.cue_index) not in used_chinese
            )
        if args.enable_part_global and remaining_english:
            if chinese_sequence:
                part_matches = aggressive_match_scope(
                    english_cues=remaining_english,
                    chinese_cues=chinese_sequence,
                    model=model,
                    embedding_store=embedding_store,
                    context_window=max(1, args.context_window - 1),
                    clip_start=0.0,
                    clip_end=max((cue.end for cue in english_cues), default=1.0),
                    match_threshold=args.part_match_threshold,
                    output_threshold=args.part_output_threshold,
                    skip_english_penalty=args.part_skip_english_penalty,
                    skip_chinese_penalty=args.part_skip_chinese_penalty,
                    progress_weight=0.22,
                    band_ratio=1.0,
                )
                apply_matches(
                    rows_by_id=rows_by_id,
                    matches=part_matches,
                    used_chinese=used_chinese,
                    origin="forced-part-global-v1",
                    origin_counter=forced_origin_counts,
                )
        run_part_tail_fill(
            english_cues=english_cues,
            chinese_sequence=chinese_sequence,
            rows_by_id=rows_by_id,
            used_chinese=used_chinese,
            min_english=args.part_tail_fill_min_english,
            min_zh_ratio=args.part_tail_fill_min_zh_ratio,
            origin_counter=forced_origin_counts,
        )

        part_rows = sorted(rows_by_id.values(), key=lambda item: (float(item["start"]), float(item["end"]), item["segment_id"]))
        matched_count = sum(1 for row in part_rows if str(row.get("status") or "") != "unmatched")
        status_counts = Counter(str(row.get("status") or "unmatched") for row in part_rows)
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

    all_rows.sort(key=lambda item: (item["part_name"], float(item["start"]), float(item["end"]), item["segment_id"]))
    total_status_counts = Counter(str(row.get("status") or "unmatched") for row in all_rows)
    matched_cues = sum(1 for row in all_rows if str(row.get("status") or "") != "unmatched")
    selected_part_names = {str(part["part_name"]) for part in selected_parts}
    base_matched = sum(
        1
        for row in base_payload.get("segments") or []
        if str(row.get("part_name") or "") in selected_part_names and str(row.get("status") or "") != "unmatched"
    )

    manifest = {
        "version": args.output_dir.name,
        "base_json": str(args.base_json),
        "mapping_json": str(args.mapping_json),
        "reviewed_master_json": str(args.reviewed_master_json),
        "english_ocr_root": str(args.english_ocr_root),
        "chinese_ocr_root": str(args.chinese_ocr_root),
        "selected_parts": [str(part["part_name"]) for part in selected_parts],
        "offline_model_only": bool(args.offline_model_only),
        "embedding_cache_path": str((args.embedding_cache_dir / f"{sanitize_model_name(args.model_name)}.pkl")) if embedding_store is not None else None,
        "total_english_cues": len(all_rows),
        "base_matched_cues": base_matched,
        "matched_cues": matched_cues,
        "coverage_ratio": round(matched_cues / max(len(all_rows), 1), 4),
        "delta_matched_cues": matched_cues - base_matched,
        "status_counts": dict(sorted(total_status_counts.items())),
        "forced_origin_counts": dict(sorted(forced_origin_counts.items())),
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
    write_json(args.output_dir / "all_segments.json", {"manifest": manifest, "segments": all_rows})
    write_tsv(args.output_dir / "all_segments.tsv", all_rows)

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
        write_json(args.output_dir / "all_segments.json", {"manifest": manifest, "segments": all_rows})

    print(json.dumps({"output_dir": str(args.output_dir), "matched_cues": matched_cues, "delta": matched_cues - base_matched}, ensure_ascii=False))


if __name__ == "__main__":
    main()
