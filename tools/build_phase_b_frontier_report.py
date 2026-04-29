from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a lightweight frontier report from current Phase B artifacts."
    )
    parser.add_argument("--master-manifest", type=Path, required=True)
    parser.add_argument("--gap-report", type=Path, required=True)
    parser.add_argument("--part04-candidate-scan", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase B Frontier Report",
        "",
        f"- Master version: `{payload['master_version']}`",
        f"- Total segments: `{payload['master_total_segment_count']}`",
        "",
        "## Current State",
        "",
    ]
    for item in payload["part_summaries"]:
        lines.append(
            f"- `{item['part_name']}`: count=`{item['segment_count']}`, largest_gap=`{item['largest_gap_duration']}`s"
        )
    lines.extend(
        [
            "",
            "## Part04 Frontier",
            "",
            f"- Current `part04` segment count: `{payload['part04']['segment_count']}`",
            f"- Current largest `part04` gap: `{payload['part04']['largest_gap_start']} -> {payload['part04']['largest_gap_end']}`",
            "",
            "### Viable Candidate Windows",
            "",
        ]
    )
    for item in payload["part04"]["viable_candidates"]:
        lines.append(
            f"- `{item['clip_name']}` from `{item['assigned_part']}` score=`{item['score']}` cut=`{item['first_cut_start']}->{item['last_cut_end']}`"
        )
    lines.extend(
        [
            "",
            "### Invalidated Trials",
            "",
        ]
    )
    for item in payload["part04"]["invalidated_trials"]:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            payload["conclusion"],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    master = _load_json(args.master_manifest)
    gap = _load_json(args.gap_report)
    scan = _load_json(args.part04_candidate_scan)

    part_summaries = []
    part04_summary = None
    for item in gap["parts"]:
        summary = item["summary"]
        row = {
            "part_name": summary["part_name"],
            "segment_count": master["part_counts"].get(summary["part_name"], 0),
            "largest_gap_start": summary["largest_gap_start"],
            "largest_gap_end": summary["largest_gap_end"],
            "largest_gap_duration": summary["largest_gap_duration"],
        }
        part_summaries.append(row)
        if summary["part_name"] == "part04":
            part04_summary = row

    viable = [
        row
        for row in scan["rows"]
        if row["clip_name"] not in {"37336780446-1-192", "37340384771-1-192", "37340906577-1-192", "37337173275-1-192"}
    ]

    payload = {
        "version": "phase-b-frontier-report-v1",
        "master_version": master["version"],
        "master_total_segment_count": master["total_segment_count"],
        "part_summaries": part_summaries,
        "part04": {
            "segment_count": master["part_counts"].get("part04", 0),
            "largest_gap_start": part04_summary["largest_gap_start"] if part04_summary else None,
            "largest_gap_end": part04_summary["largest_gap_end"] if part04_summary else None,
            "largest_gap_duration": part04_summary["largest_gap_duration"] if part04_summary else None,
            "viable_candidates": viable,
            "invalidated_trials": [
                "part04_tail_candidates_trial_v1 -> no rows",
                "part04_midgap_trial_v1 -> no rows",
            ],
        },
        "conclusion": (
            "Current evidence suggests the remaining automatic upside in part04 is limited. "
            "The strongest gains came from filter-mapped realignment and one cross-part block; "
            "subsequent mid-gap and tail-gap directed trials produced no usable rows."
        ),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(build_markdown(payload), encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")


if __name__ == "__main__":
    main()

