from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_RELEASE_SNAPSHOT_DIR = Path("scratch/phase_c_release_snapshot_v1_complete")
DEFAULT_DELIVERY_PACK_DIR = Path("scratch/phase_c_delivery_pack_v1_complete")
DEFAULT_DELTA_DIR = Path("scratch/phase_c_predecision_delta_pack_v4_complete_vs_base")
DEFAULT_HANDOFF_JSON = Path("scratch/phase_c_model_handoff_v3_complete/handoff.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_completion_report_v1_complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a final completion report for the completed Phase C deliverable.")
    parser.add_argument("--release-snapshot-dir", type=Path, default=DEFAULT_RELEASE_SNAPSHOT_DIR)
    parser.add_argument("--delivery-pack-dir", type=Path, default=DEFAULT_DELIVERY_PACK_DIR)
    parser.add_argument("--delta-dir", type=Path, default=DEFAULT_DELTA_DIR)
    parser.add_argument("--handoff-json", type=Path, default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Ghost Yotei Phase C Completion Report",
        "",
        "## Headline",
        "",
        f"- Total cues: `{report['total_cue_count']}`",
        f"- Matched cues: `{report['matched_cue_count']}`",
        f"- Unmatched cues: `{report['unmatched_cue_count']}`",
        f"- Coverage ratio: `{report['coverage_ratio']}`",
        f"- Remaining model requests: `{report['remaining_model_requests']}`",
        "",
        "## Closure",
        "",
        f"- `keep_current_match`: `{report['decision_counts'].get('keep_current_match', 0)}`",
        f"- `reject_current_match`: `{report['decision_counts'].get('reject_current_match', 0)}`",
        f"- `no_match`: `{report['decision_counts'].get('no_match', 0)}`",
        "",
        "## Delta Vs Original Base",
        "",
        f"- Changed rows: `{report['changed_row_count_vs_base']}`",
        f"- Cleared to unmatched: `{report['change_type_counts'].get('cleared-to-unmatched', 0)}`",
        f"- Metadata-only changes: `{report['change_type_counts'].get('metadata-change', 0)}`",
        "",
        "## Part Coverage",
        "",
    ]
    for row in report.get("part_stats") or []:
        lines.append(
            f"- `{row['short_name']}`: `{row['matched_count']} / {row['segment_count']} = {row['coverage_ratio']}`"
        )
    lines.extend(
        [
            "",
            "## Entry Points",
            "",
            f"- Release snapshot: `{report['release_snapshot_dir']}`",
            f"- Delivery pack: `{report['delivery_pack_dir']}`",
            f"- Delta dir: `{report['delta_dir']}`",
            f"- Handoff json: `{report['handoff_json']}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    snapshot_manifest = load_json(args.release_snapshot_dir / "manifest.json")
    delivery_manifest = load_json(args.delivery_pack_dir / "manifest.json")
    delta_manifest = load_json(args.delta_dir / "manifest.json")
    handoff = load_json(args.handoff_json)

    report = {
        "release_snapshot_dir": str(args.release_snapshot_dir),
        "delivery_pack_dir": str(args.delivery_pack_dir),
        "delta_dir": str(args.delta_dir),
        "handoff_json": str(args.handoff_json),
        "total_cue_count": snapshot_manifest.get("total_cue_count"),
        "matched_cue_count": snapshot_manifest.get("matched_cue_count"),
        "unmatched_cue_count": snapshot_manifest.get("unmatched_cue_count"),
        "coverage_ratio": snapshot_manifest.get("coverage_ratio"),
        "remaining_model_requests": snapshot_manifest.get("remaining_model_requests"),
        "decision_counts": dict(snapshot_manifest.get("decision_counts") or {}),
        "changed_row_count_vs_base": snapshot_manifest.get("changed_row_count_vs_base"),
        "change_type_counts": dict(delta_manifest.get("change_type_counts") or {}),
        "status_transition_counts": dict(delta_manifest.get("status_transition_counts") or {}),
        "part_stats": list(delivery_manifest.get("part_stats") or []),
        "next_action": handoff.get("next_action"),
    }

    part_rows = [
        {
            "part_name": row["part_name"],
            "short_name": row["short_name"],
            "segment_count": row["segment_count"],
            "matched_count": row["matched_count"],
            "unmatched_count": row["unmatched_count"],
            "coverage_ratio": row["coverage_ratio"],
        }
        for row in report["part_stats"]
    ]

    write_json(args.output_dir / "report.json", report)
    write_tsv(
        args.output_dir / "part_coverage.tsv",
        part_rows,
        ["part_name", "short_name", "segment_count", "matched_count", "unmatched_count", "coverage_ratio"],
    )
    write_markdown(args.output_dir / "REPORT.md", report)
    write_json(
        args.output_dir / "manifest.json",
        {
            "total_cue_count": report["total_cue_count"],
            "matched_cue_count": report["matched_cue_count"],
            "unmatched_cue_count": report["unmatched_cue_count"],
            "coverage_ratio": report["coverage_ratio"],
            "remaining_model_requests": report["remaining_model_requests"],
            "next_action": report["next_action"],
        },
    )
    print(f"wrote phase c completion report -> {args.output_dir}")


if __name__ == "__main__":
    main()
