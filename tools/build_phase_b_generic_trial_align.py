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
from phase_b_sequence_align import load_chinese_clip


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a generic trial cue-level alignment for a single part using ordered Chinese clips."
    )
    parser.add_argument("--part-name", type=str, required=True, help="Full part name, e.g. ghost-yotei-part04")
    parser.add_argument("--english-subdir", type=str, required=True, help="English OCR subdir, e.g. part04")
    parser.add_argument("--english-ocr-root", type=Path, required=True)
    parser.add_argument("--chinese-ocr-root", type=Path, required=True)
    parser.add_argument("--trial-clips", nargs="+", required=True)
    parser.add_argument("--selection-mode", type=str, default="generic-trial")
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


def main() -> None:
    args = parse_args()
    model = SentenceTransformer(args.model_name)
    english_cues_all = load_english_raw_cues(args.english_ocr_root / args.english_subdir / "cleaned.json")

    cursor = 0.0
    window_rows: list[dict] = []
    window_summary: list[dict] = []

    for order, clip_name in enumerate(args.trial_clips, start=1):
        chinese_all = [
            cue
            for cue in load_chinese_clip(args.chinese_ocr_root, clip_name)
            if cue.confidence >= args.min_chinese_confidence
        ]
        if not chinese_all:
            continue
        clip_start = float(chinese_all[0].start)
        clip_end = float(chinese_all[-1].end)
        clip_duration = clip_end - clip_start
        window_start = cursor
        window_end = cursor + clip_duration

        english_cues = [
            cue
            for cue in english_cues_all
            if cue.start >= window_start - args.flank_seconds and cue.start <= window_end + args.flank_seconds
        ]

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
            row["cluster_id"] = f"{args.part_name}:{clip_name}:trial{order:02d}"
            row["source_clip"] = clip_name
            row["selection_mode"] = args.selection_mode
        aligned = postprocess_cluster_rows(
            rows=aligned,
            model=model,
            chinese_lookup={cue.cue_index: cue for cue in chinese_all},
        )
        scores = [row["match_score"] for row in aligned]
        window_summary.append(
            {
                "clip_name": clip_name,
                "window_start": round(window_start, 3),
                "window_end": round(window_end, 3),
                "clip_duration": round(clip_duration, 3),
                "english_window_count": len(english_cues),
                "aligned_count": len(aligned),
                "mean_match_score": round(mean(scores), 4) if scores else None,
            }
        )
        window_rows.extend(aligned)
        cursor = window_end

    flat_rows = dedupe_rows(window_rows)
    payload = {
        "version": "phase-b-generic-trial-align-v1",
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
