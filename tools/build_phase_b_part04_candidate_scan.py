from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from filter_time_mapper import load_filter_intervals, map_original_range_to_cut_ranges


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan all clip semantic candidates for part04 and project them onto cut-time."
    )
    parser.add_argument("--mapping-json", type=Path, required=True)
    parser.add_argument("--filter-path", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-tsv", type=Path, required=True)
    parser.add_argument("--min-score", type=float, default=0.62)
    return parser.parse_args()


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "clip_name",
        "assigned_part",
        "score",
        "window_start_time",
        "window_end_time",
        "cut_ranges",
        "first_cut_start",
        "last_cut_end",
        "cut_span_seconds",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    intervals = load_filter_intervals(args.filter_path)

    rows: list[dict[str, Any]] = []
    for clip in mapping.get("clips") or []:
        assigned_part = str(clip.get("assigned_part") or "")
        for cand in clip.get("semantic_candidates") or []:
            if str(cand.get("part_name")) != "ghost-yotei-part04":
                continue
            score = float(cand.get("score") or 0.0)
            if score < args.min_score:
                continue
            start = float(cand["window_start_time"])
            end = float(cand["window_end_time"])
            cut_ranges = map_original_range_to_cut_ranges(start, end, intervals)
            if not cut_ranges:
                continue
            first_cut_start = cut_ranges[0][0]
            last_cut_end = cut_ranges[-1][1]
            rows.append(
                {
                    "clip_name": clip["clip_name"],
                    "assigned_part": assigned_part,
                    "score": round(score, 4),
                    "window_start_time": round(start, 3),
                    "window_end_time": round(end, 3),
                    "cut_ranges": cut_ranges,
                    "first_cut_start": first_cut_start,
                    "last_cut_end": last_cut_end,
                    "cut_span_seconds": round(last_cut_end - first_cut_start, 3),
                }
            )

    rows.sort(key=lambda item: (-item["score"], item["first_cut_start"], item["clip_name"]))
    payload = {
        "version": "phase-b-part04-candidate-scan-v1",
        "mapping_json": str(args.mapping_json),
        "filter_path": str(args.filter_path),
        "min_score": args.min_score,
        "candidate_count": len(rows),
        "rows": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, rows)
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()

