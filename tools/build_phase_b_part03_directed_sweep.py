from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from sentence_transformers import SentenceTransformer

from build_phase_b_part03_trial_align import run_trial_alignment


FIXED_MIDDLE = "37340906577-1-192"
FIXED_FRONT = "37340055339-1-192"

FRONT_CANDIDATES = [
    "37340055339-1-192",
    "37343464803-1-192",
    "37342021653-1-192",
    "37342874714-1-192",
]

TAIL_CANDIDATES = [
    "37343464803-1-192",
    "37342874714-1-192",
    "37342021653-1-192",
    "37343791965-1-192",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run directed front/tail sweeps around the fixed part03 middle anchor."
    )
    parser.add_argument("--english-ocr-root", type=Path, required=True)
    parser.add_argument("--chinese-ocr-root", type=Path, required=True)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_part03_directed_sweep_v1.json"),
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


def summarize(rows: list[dict[str, object]], threshold: float) -> dict[str, object]:
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

    def run_combo(combo_name: str, clips: list[str]) -> dict[str, object]:
        payload = run_trial_alignment(
            model=model,
            english_ocr_root=args.english_ocr_root,
            chinese_ocr_root=args.chinese_ocr_root,
            trial_clips=clips,
            selection_mode=combo_name,
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
        return {
            "combo_name": combo_name,
            "trial_clips": clips,
            "summary": payload["summary"],
            "highconf_080": summarize(rows, 0.80),
            "highconf_085": summarize(rows, 0.85),
        }

    front_results = []
    for front in FRONT_CANDIDATES:
        result = run_combo(f"front::{front}", [front, FIXED_MIDDLE])
        front_results.append(result)
        print(
            json.dumps(
                {
                    "kind": "front",
                    "front": front,
                    "highconf_080": result["highconf_080"]["highconf_count"],
                    "highconf_085": result["highconf_085"]["highconf_count"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    tail_results = []
    for tail in TAIL_CANDIDATES:
        result = run_combo(f"tail::{tail}", [FIXED_FRONT, FIXED_MIDDLE, tail])
        tail_results.append(result)
        print(
            json.dumps(
                {
                    "kind": "tail",
                    "tail": tail,
                    "highconf_080": result["highconf_080"]["highconf_count"],
                    "highconf_085": result["highconf_085"]["highconf_count"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    payload = {
        "version": "phase-b-part03-directed-sweep-v1",
        "fixed_middle": FIXED_MIDDLE,
        "fixed_front": FIXED_FRONT,
        "front_results": sorted(
            front_results,
            key=lambda item: (
                item["highconf_080"]["highconf_count"],
                item["highconf_085"]["highconf_count"],
                item["highconf_080"]["mean_match_score"] or 0.0,
            ),
            reverse=True,
        ),
        "tail_results": sorted(
            tail_results,
            key=lambda item: (
                item["highconf_080"]["highconf_count"],
                item["highconf_085"]["highconf_count"],
                item["highconf_080"]["mean_match_score"] or 0.0,
            ),
            reverse=True,
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.output_json}")


if __name__ == "__main__":
    main()
