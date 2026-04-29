from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a coverage gap report from a Phase B master delivery package."
    )
    parser.add_argument("--master-dir", type=Path, required=True)
    parser.add_argument("--english-ocr-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-tsv", type=Path, required=True)
    parser.add_argument("--min-gap-seconds", type=float, default=8.0)
    return parser.parse_args()


def load_part_duration(english_ocr_root: Path, short_name: str) -> float:
    cleaned_path = english_ocr_root / short_name / "cleaned.json"
    payload = json.loads(cleaned_path.read_text(encoding="utf-8"))
    cues = payload.get("cues") or []
    if not cues:
        return 0.0
    return max(float(item.get("end") or 0.0) for item in cues)


def merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not intervals:
        return []
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
            continue
        merged[-1][1] = max(merged[-1][1], end)
    return [(round(start, 3), round(end, 3)) for start, end in merged]


def invert_intervals(covered: list[tuple[float, float]], total_end: float, min_gap_seconds: float) -> list[tuple[float, float]]:
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in covered:
        if start - cursor >= min_gap_seconds:
            gaps.append((round(cursor, 3), round(start, 3)))
        cursor = max(cursor, end)
    if total_end - cursor >= min_gap_seconds:
        gaps.append((round(cursor, 3), round(total_end, 3)))
    return gaps


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "part_name",
        "coverage_end",
        "covered_seconds",
        "coverage_ratio",
        "gap_count",
        "largest_gap_start",
        "largest_gap_end",
        "largest_gap_duration",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    all_segments = json.loads((args.master_dir / "all_segments.json").read_text(encoding="utf-8"))
    segments = list(all_segments.get("segments") or [])

    part_intervals: dict[str, list[tuple[float, float]]] = {}
    for row in segments:
        part_name = str(row["part_name"]).replace("ghost-yotei-", "")
        part_intervals.setdefault(part_name, []).append((float(row["start"]), float(row["end"])))

    summary_rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for part_name in sorted(part_intervals):
        total_end = load_part_duration(args.english_ocr_root, part_name)
        covered = merge_intervals(part_intervals[part_name])
        covered_seconds = round(sum(end - start for start, end in covered), 3)
        gaps = invert_intervals(covered, total_end, args.min_gap_seconds)
        largest_gap = max(gaps, key=lambda item: item[1] - item[0]) if gaps else None
        coverage_ratio = round((covered_seconds / total_end), 4) if total_end > 0 else 0.0
        summary = {
            "part_name": part_name,
            "coverage_end": round(total_end, 3),
            "covered_seconds": covered_seconds,
            "coverage_ratio": coverage_ratio,
            "gap_count": len(gaps),
            "largest_gap_start": largest_gap[0] if largest_gap else None,
            "largest_gap_end": largest_gap[1] if largest_gap else None,
            "largest_gap_duration": round(largest_gap[1] - largest_gap[0], 3) if largest_gap else None,
        }
        summary_rows.append(summary)
        details.append(
            {
                "part_name": part_name,
                "coverage_end": round(total_end, 3),
                "covered_intervals": covered,
                "gap_intervals": gaps,
                "summary": summary,
            }
        )

    payload = {
        "version": "phase-b-gap-report-v1",
        "master_dir": str(args.master_dir),
        "english_ocr_root": str(args.english_ocr_root),
        "parts": details,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, summary_rows)
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()

