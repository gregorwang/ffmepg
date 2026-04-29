from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from sentence_transformers import SentenceTransformer

from build_phase_b_cue_local_align import (
    align_window,
    load_english_raw_cues,
    postprocess_cluster_rows,
    write_tsv,
)
from phase_b_sequence_align import load_chinese_clip


DEFAULT_TRIAL_CLIPS = [
    "37340055339-1-192",
    "37340906577-1-192",
    "37343464803-1-192",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a trial cue-level alignment for part03 using remap-inspired pseudo windows."
    )
    parser.add_argument("--english-ocr-root", type=Path, required=True)
    parser.add_argument("--chinese-ocr-root", type=Path, required=True)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_part03_trial_align_v1.json"),
    )
    parser.add_argument(
        "--output-tsv",
        type=Path,
        default=Path("scratch/phase_b_part03_trial_align_v1.tsv"),
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="paraphrase-multilingual-mpnet-base-v2",
    )
    parser.add_argument(
        "--trial-clips",
        nargs="+",
        default=DEFAULT_TRIAL_CLIPS,
        help="Ordered Chinese clip names to lay onto the part03 pseudo timeline.",
    )
    parser.add_argument(
        "--selection-mode",
        type=str,
        default="part03-trial",
    )
    parser.add_argument("--min-chinese-confidence", type=float, default=0.90)
    parser.add_argument("--flank-seconds", type=float, default=12.0)
    parser.add_argument("--max-en-group", type=int, default=3)
    parser.add_argument("--max-zh-group", type=int, default=3)
    parser.add_argument("--match-threshold", type=float, default=0.60)
    parser.add_argument("--output-threshold", type=float, default=0.68)
    parser.add_argument("--skip-en-penalty", type=float, default=0.08)
    parser.add_argument("--skip-zh-penalty", type=float, default=0.05)
    return parser.parse_args()


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    outputs: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: (item["start"], item["end"], ",".join(item["english_cue_ids"]))):
        key = (",".join(row["english_cue_ids"]), ",".join(row["chinese_cue_ids"]))
        if key in seen:
            continue
        seen.add(key)
        outputs.append(row)
    return outputs


def run_trial_alignment(
    *,
    model: SentenceTransformer,
    english_ocr_root: Path,
    chinese_ocr_root: Path,
    trial_clips: list[str],
    selection_mode: str,
    min_chinese_confidence: float,
    flank_seconds: float,
    max_en_group: int,
    max_zh_group: int,
    match_threshold: float,
    output_threshold: float,
    skip_en_penalty: float,
    skip_zh_penalty: float,
) -> dict[str, Any]:
    english_cues_all = load_english_raw_cues(english_ocr_root / "part03" / "cleaned.json")

    cursor = 0.0
    window_rows: list[dict[str, Any]] = []
    window_summary: list[dict[str, Any]] = []
    for order, clip_name in enumerate(trial_clips, start=1):
        chinese_all = [
            cue
            for cue in load_chinese_clip(chinese_ocr_root, clip_name)
            if cue.confidence >= min_chinese_confidence
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
            if cue.start >= window_start - flank_seconds and cue.start <= window_end + flank_seconds
        ]
        aligned = align_window(
            english_cues=english_cues,
            chinese_cues=chinese_all,
            model=model,
            max_en_group=max_en_group,
            max_zh_group=max_zh_group,
            match_threshold=match_threshold,
            output_threshold=output_threshold,
            skip_en_penalty=skip_en_penalty,
            skip_zh_penalty=skip_zh_penalty,
        )
        for row in aligned:
            row["part_name"] = "ghost-yotei-part03"
            row["cluster_id"] = f"ghost-yotei-part03:{clip_name}:trial{order:02d}"
            row["source_clip"] = clip_name
            row["selection_mode"] = selection_mode
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
    return {
        "version": "phase-b-part03-trial-align-v1",
        "trial_clips": trial_clips,
        "summary": window_summary,
        "flat_candidates": flat_rows,
    }


def main() -> None:
    args = parse_args()
    model = SentenceTransformer(args.model_name)
    payload = run_trial_alignment(
        model=model,
        english_ocr_root=args.english_ocr_root,
        chinese_ocr_root=args.chinese_ocr_root,
        trial_clips=list(args.trial_clips),
        selection_mode=args.selection_mode,
        min_chinese_confidence=args.min_chinese_confidence,
        flank_seconds=args.flank_seconds,
        max_en_group=args.max_en_group,
        max_zh_group=args.max_zh_group,
        match_threshold=args.match_threshold,
        output_threshold=args.output_threshold,
        skip_en_penalty=args.skip_en_penalty,
        skip_zh_penalty=args.skip_zh_penalty,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, payload["flat_candidates"])
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()
