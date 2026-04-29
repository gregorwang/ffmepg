from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from sentence_transformers import SentenceTransformer

from build_phase_b_part03_trial_align import run_trial_alignment


DEFAULT_COMBOS: list[list[str]] = [
    ["37340055339-1-192", "37340906577-1-192", "37343464803-1-192"],
    ["37340906577-1-192", "37342874714-1-192", "37343464803-1-192"],
    ["37340055339-1-192", "37340906577-1-192", "37342874714-1-192"],
    ["37340906577-1-192", "37342021653-1-192", "37343464803-1-192"],
    ["37338680721-1-192", "37340055339-1-192", "37343464803-1-192"],
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep several candidate clip triples for part03 and compare trial alignment quality."
    )
    parser.add_argument("--english-ocr-root", type=Path, required=True)
    parser.add_argument("--chinese-ocr-root", type=Path, required=True)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_part03_combo_sweep_v1.json"),
    )
    parser.add_argument(
        "--max-combos",
        type=int,
        default=None,
        help="Optionally limit how many candidate combos to run from the top of the default list.",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="paraphrase-multilingual-mpnet-base-v2",
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


def summarize_rows(rows: list[dict[str, object]], threshold: float) -> dict[str, object]:
    high = [row for row in rows if float(row["match_score"]) >= threshold]
    return {
        "count": len(rows),
        "mean_match_score": round(mean(float(row["match_score"]) for row in rows), 4) if rows else None,
        "highconf_count": len(high),
        "highconf_sources": sorted({str(row["source_clip"]) for row in high}),
    }


def main() -> None:
    args = parse_args()
    model = SentenceTransformer(args.model_name)
    combo_results: list[dict[str, object]] = []
    combos = DEFAULT_COMBOS[: args.max_combos] if args.max_combos else DEFAULT_COMBOS

    for index, combo in enumerate(combos, start=1):
        payload = run_trial_alignment(
            model=model,
            english_ocr_root=args.english_ocr_root,
            chinese_ocr_root=args.chinese_ocr_root,
            trial_clips=combo,
            selection_mode=f"part03-sweep-{index:02d}",
            min_chinese_confidence=args.min_chinese_confidence,
            flank_seconds=args.flank_seconds,
            max_en_group=args.max_en_group,
            max_zh_group=args.max_zh_group,
            match_threshold=args.match_threshold,
            output_threshold=args.output_threshold,
            skip_en_penalty=args.skip_en_penalty,
            skip_zh_penalty=args.skip_zh_penalty,
        )
        rows = list(payload["flat_candidates"])
        combo_results.append(
            {
                "combo_index": index,
                "trial_clips": combo,
                "summary": payload["summary"],
                "all_rows": summarize_rows(rows, threshold=0.0),
                "highconf_080": summarize_rows(rows, threshold=0.80),
                "highconf_085": summarize_rows(rows, threshold=0.85),
            }
        )
        print(
            json.dumps(
                {
                    "combo_index": index,
                    "trial_clips": combo,
                    "highconf_080": combo_results[-1]["highconf_080"]["highconf_count"],
                    "highconf_085": combo_results[-1]["highconf_085"]["highconf_count"],
                    "mean_match_score": combo_results[-1]["all_rows"]["mean_match_score"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    combo_results.sort(
        key=lambda item: (
            item["highconf_080"]["highconf_count"],
            item["highconf_085"]["highconf_count"],
            item["all_rows"]["mean_match_score"] or 0.0,
        ),
        reverse=True,
    )
    payload = {
        "version": "phase-b-part03-combo-sweep-v1",
        "combos": combo_results,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.output_json}")


if __name__ == "__main__":
    main()
