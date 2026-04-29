from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from sentence_transformers import SentenceTransformer

from build_phase_b_cue_local_align import (
    align_window,
    load_english_raw_cues,
    postprocess_cluster_rows,
    write_tsv,
)
from filter_time_mapper import load_filter_intervals, map_original_range_to_cut_ranges
from phase_b_sequence_align import load_chinese_clip


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a filter-mapped local cue alignment using original-time semantic windows projected to cut-time."
    )
    parser.add_argument("--mapping-json", type=Path, required=True)
    parser.add_argument("--part-name", type=str, required=True)
    parser.add_argument("--filter-path", type=Path, required=True)
    parser.add_argument("--english-subdir", type=str, required=True)
    parser.add_argument("--english-ocr-root", type=Path, required=True)
    parser.add_argument("--chinese-ocr-root", type=Path, required=True)
    parser.add_argument("--trial-clips", nargs="+", required=True)
    parser.add_argument("--selection-mode", type=str, default="filter-mapped-trial")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-tsv", type=Path, required=True)
    parser.add_argument("--model-name", type=str, default="paraphrase-multilingual-mpnet-base-v2")
    parser.add_argument("--min-chinese-confidence", type=float, default=0.90)
    parser.add_argument("--flank-seconds", type=float, default=12.0)
    parser.add_argument("--max-en-group", type=int, default=3)
    parser.add_argument("--max-zh-group", type=int, default=3)
    parser.add_argument("--match-threshold", type=float, default=0.60)
    parser.add_argument("--output-threshold", type=float, default=0.68)
    parser.add_argument("--skip-en-penalty", type=float, default=0.08)
    parser.add_argument("--skip-zh-penalty", type=float, default=0.05)
    return parser.parse_args()


def dedupe_rows(rows: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    outputs: list[dict] = []
    for row in sorted(rows, key=lambda item: (item["start"], item["end"], ",".join(item["english_cue_ids"]))):
        key = (",".join(row["english_cue_ids"]), ",".join(row["chinese_cue_ids"]))
        if key in seen:
            continue
        seen.add(key)
        outputs.append(row)
    return outputs


def _select_part_candidate(clip_info: dict, part_name: str) -> dict | None:
    candidates = [cand for cand in clip_info.get("semantic_candidates", []) if str(cand.get("part_name")) == part_name]
    if not candidates:
        return None
    return max(candidates, key=lambda item: float(item.get("score") or 0.0))


def _cue_in_ranges(start: float, cut_ranges: list[tuple[float, float]], flank_seconds: float) -> bool:
    return any((range_start - flank_seconds) <= start <= (range_end + flank_seconds) for range_start, range_end in cut_ranges)


def main() -> None:
    args = parse_args()
    model = SentenceTransformer(args.model_name)
    english_cues_all = load_english_raw_cues(args.english_ocr_root / args.english_subdir / "cleaned.json")
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    clip_lookup = {str(item["clip_name"]): item for item in mapping.get("clips") or []}
    filter_intervals = load_filter_intervals(args.filter_path)

    window_rows: list[dict] = []
    window_summary: list[dict] = []

    for order, clip_name in enumerate(args.trial_clips, start=1):
        clip_info = clip_lookup.get(clip_name)
        if clip_info is None:
            continue
        candidate = _select_part_candidate(clip_info, args.part_name)
        if candidate is None:
            continue

        chinese_all = [
            cue
            for cue in load_chinese_clip(args.chinese_ocr_root, clip_name)
            if cue.confidence >= args.min_chinese_confidence
        ]
        if not chinese_all:
            continue

        original_start = float(candidate["window_start_time"])
        original_end = float(candidate["window_end_time"])
        cut_ranges = map_original_range_to_cut_ranges(
            original_start=original_start,
            original_end=original_end,
            intervals=filter_intervals,
        )
        if not cut_ranges:
            window_summary.append(
                {
                    "clip_name": clip_name,
                    "semantic_candidate_score": round(float(candidate.get("score") or 0.0), 4),
                    "original_window_start": round(original_start, 3),
                    "original_window_end": round(original_end, 3),
                    "cut_ranges": [],
                    "english_window_count": 0,
                    "aligned_count": 0,
                    "mean_match_score": None,
                }
            )
            continue

        english_cues = [cue for cue in english_cues_all if _cue_in_ranges(cue.start, cut_ranges, args.flank_seconds)]

        aligned = align_window(
            english_cues=english_cues,
            chinese_cues=chinese_all,
            model=model,
            max_en_group=args.max_en_group,
            max_zh_group=args.max_zh_group,
            match_threshold=args.match_threshold,
            output_threshold=args.output_threshold,
            skip_en_penalty=args.skip_en_penalty,
            skip_zh_penalty=args.skip_zh_penalty,
        )
        for row in aligned:
            row["part_name"] = args.part_name
            row["cluster_id"] = f"{args.part_name}:{clip_name}:mapped{order:02d}"
            row["source_clip"] = clip_name
            row["selection_mode"] = args.selection_mode
            row["semantic_window_original"] = [round(original_start, 3), round(original_end, 3)]
            row["semantic_window_cut_ranges"] = [list(item) for item in cut_ranges]
        aligned = postprocess_cluster_rows(
            rows=aligned,
            model=model,
            chinese_lookup={cue.cue_index: cue for cue in chinese_all},
        )
        scores = [row["match_score"] for row in aligned]
        window_summary.append(
            {
                "clip_name": clip_name,
                "semantic_candidate_score": round(float(candidate.get("score") or 0.0), 4),
                "original_window_start": round(original_start, 3),
                "original_window_end": round(original_end, 3),
                "cut_ranges": [list(item) for item in cut_ranges],
                "english_window_count": len(english_cues),
                "aligned_count": len(aligned),
                "mean_match_score": round(mean(scores), 4) if scores else None,
            }
        )
        window_rows.extend(aligned)

    flat_rows = dedupe_rows(window_rows)
    payload = {
        "version": "phase-b-filter-mapped-trial-align-v1",
        "part_name": args.part_name,
        "trial_clips": list(args.trial_clips),
        "summary": window_summary,
        "flat_candidates": flat_rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, flat_rows)
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()

