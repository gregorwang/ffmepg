from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from build_phase_c_fulltrack_rebuild import (
    DEFAULT_EMBEDDING_CACHE_DIR,
    EmbeddingStore,
    encode_texts,
    load_sentence_model,
    sanitize_model_name,
)
from phase_b_sequence_align import prepare_chinese_text, prepare_english_text, speaker_compatible


DEFAULT_BUNDLE_ROOT = Path("scratch/phase_c_clip_review_bundles_v1")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_clip_candidate_packs_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build candidate packs for low-coverage Phase C clip review bundles.")
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--clips", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model-name", type=str, default="paraphrase-multilingual-MiniLM-L12-v2")
    parser.add_argument("--offline-model-only", action="store_true", default=True)
    parser.add_argument("--embedding-cache-dir", type=Path, default=DEFAULT_EMBEDDING_CACHE_DIR)
    parser.add_argument("--search-pad", type=int, default=8)
    parser.add_argument("--max-english-block-size", type=int, default=10)
    parser.add_argument("--max-chinese-span", type=int, default=4)
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def build_row_slice_lookup(review_rows: list[dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    cue_index = {str(row["english_cue_id"]): idx for idx, row in enumerate(review_rows)}
    return cue_index, review_rows


def chinese_position_lookup(chinese_cues: list[dict[str, Any]]) -> dict[int, int]:
    return {int(row["cue_index"]): idx for idx, row in enumerate(chinese_cues)}


def english_block_rows(
    block: dict[str, Any],
    cue_index: dict[str, int],
    review_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    start_idx = cue_index[str(block["english_start_cue_id"])]
    end_idx = cue_index[str(block["english_end_cue_id"])]
    return review_rows[start_idx : end_idx + 1]


def block_english_text(rows: list[dict[str, Any]]) -> str:
    return " ".join(str(row.get("english_text") or "").strip() for row in rows if str(row.get("english_text") or "").strip()).strip()


def block_duration(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return max(0.0, float(rows[-1]["end"]) - float(rows[0]["start"]))


def split_large_block(
    block: dict[str, Any],
    rows: list[dict[str, Any]],
    max_english_block_size: int,
) -> list[dict[str, Any]]:
    if len(rows) <= max_english_block_size:
        return [dict(block)]

    outputs: list[dict[str, Any]] = []
    chunk_size = max(max_english_block_size, 1)
    for idx, start in enumerate(range(0, len(rows), chunk_size), start=1):
        chunk = rows[start : start + chunk_size]
        outputs.append(
            {
                **block,
                "block_id": f"{block['block_id']}_sub{idx:02d}",
                "english_start_cue_id": chunk[0]["english_cue_id"],
                "english_end_cue_id": chunk[-1]["english_cue_id"],
                "english_count": len(chunk),
                "english_start_time": float(chunk[0]["start"]),
                "english_end_time": float(chunk[-1]["end"]),
                "english_preview": " ".join(str(row.get("english_text") or "") for row in chunk[:3]).strip(),
            }
        )
    return outputs


def anchored_search_bounds(
    block: dict[str, Any],
    rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    cue_index: dict[str, int],
    chinese_pos: dict[int, int],
    total_chinese: int,
    search_pad: int,
) -> tuple[int, int]:
    start_idx = cue_index[str(block["english_start_cue_id"])]
    end_idx = cue_index[str(block["english_end_cue_id"])]

    left_anchor: int | None = None
    for idx in range(start_idx - 1, -1, -1):
        row = review_rows[idx]
        cue_ids = [int(item) for item in str(row.get("chinese_cue_ids") or "").split(",") if item.strip().isdigit()]
        positions = [chinese_pos[item] for item in cue_ids if item in chinese_pos]
        if positions:
            left_anchor = max(positions)
            break

    right_anchor: int | None = None
    for idx in range(end_idx + 1, len(review_rows)):
        row = review_rows[idx]
        cue_ids = [int(item) for item in str(row.get("chinese_cue_ids") or "").split(",") if item.strip().isdigit()]
        positions = [chinese_pos[item] for item in cue_ids if item in chinese_pos]
        if positions:
            right_anchor = min(positions)
            break

    est_start = max(0, int(block["estimated_chinese_start_pos"]) - search_pad)
    est_end = min(total_chinese, int(block["estimated_chinese_end_pos"]) + search_pad + 1)
    lower = max(est_start, 0 if left_anchor is None else left_anchor + 1)
    upper = min(est_end, total_chinese if right_anchor is None else right_anchor)
    if lower >= upper:
        return est_start, est_end
    return lower, upper


def chinese_span_text(chinese_rows: list[dict[str, Any]]) -> str:
    return " ".join(str(row.get("text") or "").strip() for row in chinese_rows if str(row.get("text") or "").strip()).strip()


def chinese_span_duration(chinese_rows: list[dict[str, Any]]) -> float:
    if not chinese_rows:
        return 0.0
    return max(0.0, float(chinese_rows[-1]["end"]) - float(chinese_rows[0]["start"]))


def score_candidate(
    english_text: str,
    english_duration: float,
    english_vec: np.ndarray,
    chinese_rows: list[dict[str, Any]],
    chinese_vec: np.ndarray,
    block: dict[str, Any],
    local_start_pos: int,
    local_end_pos: int,
) -> float:
    semantic = float(np.dot(english_vec, chinese_vec))
    if semantic < 0.36:
        return -1e9

    speaker_bonus = 0.03 if speaker_compatible(english_text, chinese_span_text(chinese_rows)) else -0.05
    zh_duration = chinese_span_duration(chinese_rows)
    duration_ratio = min(max(english_duration, 0.25), max(zh_duration, 0.25)) / max(max(english_duration, 0.25), max(zh_duration, 0.25))

    target_center = (int(block["estimated_chinese_start_pos"]) + int(block["estimated_chinese_end_pos"])) * 0.5
    actual_center = (local_start_pos + local_end_pos) * 0.5
    center_span = max(float(block["estimated_chinese_count"]) * 0.75, 6.0)
    progress_score = max(0.0, 1.0 - (abs(target_center - actual_center) / center_span))

    return (0.78 * semantic) + (0.12 * progress_score) + (0.07 * duration_ratio) + speaker_bonus


def build_clip_candidates(
    bundle_dir: Path,
    output_dir: Path,
    model_name: str,
    offline_model_only: bool,
    embedding_cache_dir: Path,
    search_pad: int,
    max_english_block_size: int,
    max_chinese_span: int,
    top_k: int,
) -> dict[str, Any]:
    payload = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    manifest = dict(payload["manifest"])
    review_rows = list(payload["review_rows"])
    chinese_cues = list(payload["chinese_cues"])
    unmatched_blocks = list(payload["unmatched_blocks"])

    model = load_sentence_model(model_name, offline_model_only)
    cache_path = embedding_cache_dir / f"{sanitize_model_name(model_name)}.pkl"
    embedding_store = EmbeddingStore.load(cache_path)

    cue_index, ordered_rows = build_row_slice_lookup(review_rows)
    chinese_pos = chinese_position_lookup(chinese_cues)
    candidate_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    skip_counts: Counter[str] = Counter()

    english_texts: list[str] = []
    chinese_texts: list[str] = []
    pending_blocks: list[tuple[dict[str, Any], list[dict[str, Any]], str, float, list[tuple[int, int, list[dict[str, Any]], str]]]] = []

    expanded_blocks: list[dict[str, Any]] = []
    for block in unmatched_blocks:
        rows = english_block_rows(block, cue_index, ordered_rows)
        expanded_blocks.extend(split_large_block(block, rows, max_english_block_size))

    for block in expanded_blocks:
        rows = english_block_rows(block, cue_index, ordered_rows)
        english_text = block_english_text(rows)
        english_sem = prepare_english_text(english_text)
        if not english_sem:
            skip_counts["empty-english-semantic"] += 1
            block_rows.append(
                {
                    **block,
                    "candidate_count": 0,
                    "top_score": None,
                    "decision": "skipped-empty-english-semantic",
                }
            )
            continue
        start_pos, end_pos = anchored_search_bounds(
            block=block,
            rows=rows,
            review_rows=ordered_rows,
            cue_index=cue_index,
            chinese_pos=chinese_pos,
            total_chinese=len(chinese_cues),
            search_pad=search_pad,
        )
        local_chinese = chinese_cues[start_pos:end_pos]
        candidate_spans: list[tuple[int, int, list[dict[str, Any]], str]] = []
        for local_start in range(len(local_chinese)):
            for span_size in range(1, max_chinese_span + 1):
                local_end = local_start + span_size
                if local_end > len(local_chinese):
                    break
                rows_span = local_chinese[local_start:local_end]
                if any(bool(row.get("used_by_current_match")) for row in rows_span):
                    continue
                span_text = chinese_span_text(rows_span)
                span_sem = prepare_chinese_text(span_text)
                if not span_sem:
                    continue
                candidate_spans.append((start_pos + local_start, start_pos + local_end - 1, rows_span, span_sem))
                chinese_texts.append(span_sem)

        if not candidate_spans:
            skip_counts["no-chinese-candidates"] += 1
            block_rows.append(
                {
                    **block,
                    "candidate_count": 0,
                    "top_score": None,
                    "decision": "skipped-no-chinese-candidates",
                }
            )
            continue

        english_texts.append(english_sem)
        pending_blocks.append((block, rows, english_sem, block_duration(rows), candidate_spans))

    unique_english = [text for text in dict.fromkeys(english_texts)]
    unique_chinese = [text for text in dict.fromkeys(chinese_texts)]
    english_matrix = encode_texts(model, unique_english, 128, embedding_store)
    chinese_matrix = encode_texts(model, unique_chinese, 128, embedding_store)
    english_vecs = {text: english_matrix[idx] for idx, text in enumerate(unique_english)}
    chinese_vecs = {text: chinese_matrix[idx] for idx, text in enumerate(unique_chinese)}

    for block, rows, english_sem, english_duration, candidate_spans in pending_blocks:
        english_text = block_english_text(rows)
        english_vec = english_vecs[english_sem]
        ranked: list[dict[str, Any]] = []
        for global_start, global_end, chinese_rows, chinese_sem in candidate_spans:
            chinese_vec = chinese_vecs[chinese_sem]
            score = score_candidate(
                english_text=english_text,
                english_duration=english_duration,
                english_vec=english_vec,
                chinese_rows=chinese_rows,
                chinese_vec=chinese_vec,
                block=block,
                local_start_pos=global_start,
                local_end_pos=global_end,
            )
            if score <= -1e8:
                continue
            ranked.append(
                {
                    "block_id": block["block_id"],
                    "english_start_cue_id": block["english_start_cue_id"],
                    "english_end_cue_id": block["english_end_cue_id"],
                    "english_count": block["english_count"],
                    "candidate_start_pos": global_start,
                    "candidate_end_pos": global_end,
                    "candidate_chinese_count": len(chinese_rows),
                    "candidate_cue_indices": ",".join(str(row["cue_index"]) for row in chinese_rows),
                    "candidate_score": round(score, 4),
                    "english_text": english_text,
                    "chinese_text": chinese_span_text(chinese_rows),
                }
            )
        ranked.sort(key=lambda row: row["candidate_score"], reverse=True)
        top_candidates = ranked[:top_k]
        candidate_rows.extend(top_candidates)
        block_rows.append(
            {
                **block,
                "candidate_count": len(top_candidates),
                "top_score": top_candidates[0]["candidate_score"] if top_candidates else None,
                "decision": "ok" if top_candidates else "no-scored-candidates",
            }
        )

    embedding_store.save()
    clip_output_dir = output_dir / manifest["clip_name"]
    write_json(
        clip_output_dir / "manifest.json",
        {
            "clip_name": manifest["clip_name"],
            "part_name": manifest["part_name"],
            "block_count": len(unmatched_blocks),
            "expanded_block_count": len(expanded_blocks),
            "candidate_block_count": sum(1 for row in block_rows if row["candidate_count"]),
            "candidate_row_count": len(candidate_rows),
            "skip_counts": dict(sorted(skip_counts.items())),
            "embedding_cache_path": str(cache_path),
            "embedding_cache_stats": {
                "cache_hits": embedding_store.cache_hits,
                "cache_misses": embedding_store.cache_misses,
                "save_count": embedding_store.save_count,
                "stored_texts": len(embedding_store.vectors),
            },
        },
    )
    write_json(
        clip_output_dir / "candidates.json",
        {
            "manifest": manifest,
            "block_rows": block_rows,
            "candidate_rows": candidate_rows,
        },
    )
    write_tsv(
        clip_output_dir / "candidate_blocks.tsv",
        block_rows,
        [
            "block_id",
            "english_start_cue_id",
            "english_end_cue_id",
            "english_count",
            "english_start_time",
            "english_end_time",
            "english_preview",
            "estimated_chinese_start_pos",
            "estimated_chinese_end_pos",
            "estimated_chinese_count",
            "estimated_chinese_preview",
            "candidate_count",
            "top_score",
            "decision",
        ],
    )
    write_tsv(
        clip_output_dir / "candidate_rows.tsv",
        candidate_rows,
        [
            "block_id",
            "english_start_cue_id",
            "english_end_cue_id",
            "english_count",
            "candidate_start_pos",
            "candidate_end_pos",
            "candidate_chinese_count",
            "candidate_cue_indices",
            "candidate_score",
            "english_text",
            "chinese_text",
        ],
    )
    return json.loads((clip_output_dir / "manifest.json").read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    clip_manifests = []
    for clip_name in args.clips:
        clip_manifests.append(
            build_clip_candidates(
                bundle_dir=args.bundle_root / clip_name,
                output_dir=args.output_dir,
                model_name=args.model_name,
                offline_model_only=args.offline_model_only,
                embedding_cache_dir=args.embedding_cache_dir,
                search_pad=args.search_pad,
                max_english_block_size=args.max_english_block_size,
                max_chinese_span=args.max_chinese_span,
                top_k=args.top_k,
            )
        )

    write_json(
        args.output_dir / "manifest.json",
        {
            "clip_count": len(clip_manifests),
            "clips": clip_manifests,
        },
    )
    print(f"wrote candidate packs -> {args.output_dir}")


if __name__ == "__main__":
    main()
