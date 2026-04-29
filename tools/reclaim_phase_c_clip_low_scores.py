from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from build_phase_c_english_first_forced_rematch import (
    clone_row,
    parse_args as _unused_parse_args,
    run_clip_gap_rescue,
    run_clip_group_gap_rescue,
    run_clip_micro_gap_fill,
    run_clip_tail_fill,
    run_clip_window_pass,
    run_part_tail_fill,
)
from build_phase_c_fulltrack_rebuild import (
    DEFAULT_CHINESE_OCR_ROOT,
    DEFAULT_EMBEDDING_CACHE_DIR,
    DEFAULT_ENGLISH_OCR_ROOT,
    DEFAULT_MAPPING_JSON,
    EmbeddingStore,
    assign_clip_english_cues,
    load_full_chinese_cues,
    load_full_english_cues,
    load_sentence_model,
    part_short_name,
    sanitize_model_name,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reclaim low-score forced rows in one clip, then rerun local rematch.")
    parser.add_argument("--base-json", type=Path, required=True)
    parser.add_argument("--mapping-json", type=Path, default=DEFAULT_MAPPING_JSON)
    parser.add_argument("--english-ocr-root", type=Path, default=DEFAULT_ENGLISH_OCR_ROOT)
    parser.add_argument("--chinese-ocr-root", type=Path, default=DEFAULT_CHINESE_OCR_ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--part-name", type=str, required=True)
    parser.add_argument("--clip-name", type=str, required=True)
    parser.add_argument("--threshold", type=float, default=0.20)
    parser.add_argument("--model-name", type=str, default="paraphrase-multilingual-MiniLM-L12-v2")
    parser.add_argument("--offline-model-only", action="store_true")
    parser.add_argument("--embedding-cache-dir", type=Path, default=DEFAULT_EMBEDDING_CACHE_DIR)
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    base_payload = json.loads(args.base_json.read_text(encoding="utf-8"))
    base_rows = [dict(row) for row in base_payload.get("segments") or []]
    rows_by_key = {(str(row["part_name"]), str(row["segment_id"])): dict(row) for row in base_rows}

    english_cues = load_full_english_cues(args.english_ocr_root, args.part_name)
    clip_assignments = sorted(
        [item for item in mapping.get("clips") or [] if str(item.get("assigned_part") or "") == args.part_name],
        key=lambda item: int(item.get("clip_order_in_part") or 0),
    )
    english_by_clip = assign_clip_english_cues(english_cues, clip_assignments)
    clip_english = list(english_by_clip.get(args.clip_name, []))
    if not clip_english:
        raise SystemExit(f"clip not found in part mapping: {args.clip_name}")
    clip_chinese = list(load_full_chinese_cues(args.chinese_ocr_root, args.clip_name))

    model = load_sentence_model(args.model_name, args.offline_model_only)
    cache_path = args.embedding_cache_dir / f"{sanitize_model_name(args.model_name)}.pkl"
    embedding_store = EmbeddingStore.load(cache_path)

    rows_by_id: dict[str, dict[str, Any]] = {
        cue.cue_id: clone_row(rows_by_key.get((args.part_name, cue.cue_id)) or {}, cue)
        for cue in english_cues
    }

    reclaimed_rows: list[dict[str, Any]] = []
    for cue in clip_english:
        row = rows_by_id[cue.cue_id]
        origin = str(row.get("match_origin") or "")
        score = float(row.get("match_score") or 0.0)
        if row.get("source_clip") != args.clip_name:
            continue
        if not origin.startswith("forced-"):
            continue
        if score > args.threshold:
            continue
        reclaimed_rows.append(
            {
                "english_cue_id": cue.cue_id,
                "origin": origin,
                "score": score,
                "english_text": cue.text,
                "chinese_text": str(row.get("chinese_text") or ""),
            }
        )
        row["status"] = "unmatched"
        row["match_origin"] = "reclaimed-low-score-v1"
        row["match_score"] = None
        row["chinese_confidence"] = None
        row["source_clip"] = None
        row["chinese_text"] = ""
        row["chinese_cue_ids"] = []
        row["group_english_cue_ids"] = [cue.cue_id]
        row["notes"] = f"reclaimed-low-score <= {args.threshold}"

    used_chinese: set[tuple[str, int]] = set()
    for row in rows_by_id.values():
        if str(row.get("status") or "") == "unmatched":
            continue
        source_clip = str(row.get("source_clip") or "")
        for cue_id in row.get("chinese_cue_ids") or []:
            text = str(cue_id).strip()
            if source_clip and text.isdigit():
                used_chinese.add((source_clip, int(text)))

    forced_origin_counts: Counter[str] = Counter()
    run_clip_window_pass(
        clip_name=args.clip_name,
        clip_english=clip_english,
        clip_chinese=clip_chinese,
        rows_by_id=rows_by_id,
        used_chinese=used_chinese,
        model=model,
        embedding_store=embedding_store,
        context_window=2,
        match_threshold=0.06,
        output_threshold=0.12,
        skip_english_penalty=0.004,
        skip_chinese_penalty=0.002,
        progress_weight=0.28,
        origin_counter=forced_origin_counts,
        origin_name="reclaim-rerun-clip-window-v1",
        chunk_target_size=64,
    )
    run_clip_gap_rescue(
        clip_name=args.clip_name,
        clip_english=clip_english,
        clip_chinese=clip_chinese,
        rows_by_id=rows_by_id,
        used_chinese=used_chinese,
        model=model,
        embedding_store=embedding_store,
        context_window=2,
        min_run=3,
        chunk_target_size=64,
        origin_counter=forced_origin_counts,
    )
    run_clip_group_gap_rescue(
        clip_name=args.clip_name,
        clip_english=clip_english,
        clip_chinese=clip_chinese,
        rows_by_id=rows_by_id,
        used_chinese=used_chinese,
        model=model,
        embedding_store=embedding_store,
        min_run=2,
        origin_counter=forced_origin_counts,
    )
    run_clip_micro_gap_fill(
        clip_name=args.clip_name,
        clip_english=clip_english,
        clip_chinese=clip_chinese,
        rows_by_id=rows_by_id,
        used_chinese=used_chinese,
        max_run=2,
        max_zh=3,
        origin_counter=forced_origin_counts,
    )
    run_clip_tail_fill(
        clip_name=args.clip_name,
        clip_english=clip_english,
        clip_chinese=clip_chinese,
        rows_by_id=rows_by_id,
        used_chinese=used_chinese,
        min_english=20,
        min_zh_ratio=0.8,
        origin_counter=forced_origin_counts,
    )

    all_rows = sorted(rows_by_id.values(), key=lambda item: (item["part_name"], float(item["start"]), float(item["end"]), item["segment_id"]))
    matched_cues = sum(1 for row in all_rows if str(row.get("status") or "") != "unmatched")
    manifest = {
        "version": args.output_dir.name,
        "base_json": str(args.base_json),
        "part_name": args.part_name,
        "clip_name": args.clip_name,
        "threshold": args.threshold,
        "reclaimed_row_count": len(reclaimed_rows),
        "matched_cues": matched_cues,
        "forced_origin_counts": dict(sorted(forced_origin_counts.items())),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "all_segments.json", {"manifest": manifest, "segments": all_rows})
    write_json(args.output_dir / "reclaimed_rows.json", {"rows": reclaimed_rows})
    print(json.dumps({"output_dir": str(args.output_dir), "reclaimed": len(reclaimed_rows), "matched_cues": matched_cues}, ensure_ascii=False))


if __name__ == "__main__":
    main()
