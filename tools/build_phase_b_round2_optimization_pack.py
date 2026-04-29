from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a second-round optimization pack from a reviewed Phase B master baseline."
    )
    parser.add_argument("--reviewed-master-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--version-label",
        type=str,
        default="phase-b-round2-optimization-pack-v1",
        help="Version label written into the pack manifest.",
    )
    parser.add_argument(
        "--auto-threshold",
        type=float,
        default=0.80,
        help="Upper match-score threshold for auto-accepted rows that should be rechecked.",
    )
    parser.add_argument(
        "--part04-threshold",
        type=float,
        default=0.76,
        help="Upper match-score threshold for confirmed part04 rows that should be rechecked.",
    )
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "round2_id",
        "bucket",
        "priority",
        "part_name",
        "current_status",
        "match_score",
        "selection_mode",
        "alignment_type",
        "review_action",
        "global_segment_id",
        "source_clip",
        "english_text",
        "chinese_text",
        "review_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def compact_part_name(part_name: str) -> str:
    return part_name.replace("ghost-yotei-", "")


def to_candidate(
    row: dict[str, Any],
    *,
    index: int,
    bucket: str,
    priority: str,
    review_action: str,
    reason_tags: list[str],
) -> dict[str, Any]:
    return {
        "round2_id": f"r2_{index:04d}",
        "curation_id": f"round2_{index:04d}",
        "bucket": bucket,
        "priority": priority,
        "reason_tags": reason_tags,
        "review_action": review_action,
        "global_segment_id": row["global_segment_id"],
        "part_name": row["part_name"],
        "part_short_name": compact_part_name(row["part_name"]),
        "quality_label": row["quality_label"],
        "selection_mode": row["selection_mode"],
        "alignment_type": row.get("alignment_type", ""),
        "source_pack": row.get("source_pack", ""),
        "source_clip": row["source_clip"],
        "start": row["start"],
        "end": row["end"],
        "duration": row["duration"],
        "match_score": row["match_score"],
        "english_cue_ids": list(row.get("english_cue_ids") or []),
        "chinese_cue_ids": list(row.get("chinese_cue_ids") or []),
        "english_text": row["english_text"],
        "chinese_text": row["chinese_text"],
        "current_status": row["review_status"],
        "review_notes": row.get("review_notes", ""),
    }


def build_readme(manifest: dict[str, Any], batches: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase B Round 2 Optimization Pack",
        "",
        f"- Version: `{manifest['version']}`",
        f"- Source reviewed master: `{manifest['source_reviewed_master_json']}`",
        f"- Total candidate count: `{manifest['candidate_count']}`",
        "",
        "## Why these rows",
        "",
        "- `revised-core`: already manually revised once; useful for second-pass wording/consistency checks.",
        "- `autoaccepted-lowscore`: still auto-accepted, but score is below the chosen threshold.",
        "- `part04-confirmed-lowscore`: already confirmed, but part04 remains the weakest area and these rows sit near the low-score edge.",
        "",
        "## Batch summary",
        "",
    ]
    for batch in batches:
        lines.extend(
            [
                f"- `{batch['name']}`: `{batch['item_count']}` rows",
                f"  scope: `{batch['scope_note']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `manifest.json`: aggregate pack statistics",
            "- `candidates.json`: full machine-readable candidate list",
            "- `candidates.tsv`: tabular candidate list",
            "- `batches/*.json`: second-round review batches",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    payload = json.loads(args.reviewed_master_json.read_text(encoding="utf-8"))
    source_rows = list(payload.get("segments") or [])

    revised_rows = [row for row in source_rows if row.get("review_status") == "revised"]
    autoaccepted_lowscore_rows = [
        row
        for row in source_rows
        if row.get("review_status") == "auto-accepted" and float(row.get("match_score", 0.0)) < args.auto_threshold
    ]
    part04_confirmed_lowscore_rows = [
        row
        for row in source_rows
        if row.get("review_status") == "confirmed"
        and row.get("part_name") == "ghost-yotei-part04"
        and float(row.get("match_score", 0.0)) < args.part04_threshold
    ]

    revised_rows.sort(key=lambda row: (row["part_name"], row["start"], row["global_segment_id"]))
    autoaccepted_lowscore_rows.sort(key=lambda row: (row["part_name"], row["match_score"], row["global_segment_id"]))
    part04_confirmed_lowscore_rows.sort(key=lambda row: (row["start"], row["global_segment_id"]))

    candidates: list[dict[str, Any]] = []
    next_index = 1
    bucket_specs = [
        (
            "revised-core",
            "high",
            "validate_manual_revision",
            ["revised-row", "second-pass-wording"],
            revised_rows,
        ),
        (
            "autoaccepted-lowscore",
            "medium",
            "spot_check_low_score_auto",
            ["auto-accepted", "low-score-edge"],
            autoaccepted_lowscore_rows,
        ),
        (
            "part04-confirmed-lowscore",
            "high",
            "stress_test_part04_confirmed",
            ["part04", "confirmed-low-score"],
            part04_confirmed_lowscore_rows,
        ),
    ]

    batches: list[dict[str, Any]] = []
    for batch_index, (bucket, priority, review_action, reason_tags, rows) in enumerate(bucket_specs, start=1):
        items: list[dict[str, Any]] = []
        for row in rows:
            candidate = to_candidate(
                row,
                index=next_index,
                bucket=bucket,
                priority=priority,
                review_action=review_action,
                reason_tags=reason_tags,
            )
            candidates.append(candidate)
            items.append(candidate)
            next_index += 1

        if not items:
            continue

        batch_name = f"round2_batch_{batch_index:02d}_{bucket}"
        scope_note = {
            "revised-core": "Rows that were already revised once and benefit from one more consistency pass.",
            "autoaccepted-lowscore": f"Auto-accepted rows with match_score < {args.auto_threshold:.2f}.",
            "part04-confirmed-lowscore": f"Confirmed part04 rows with match_score < {args.part04_threshold:.2f}.",
        }[bucket]
        batch_payload = {
            "version": args.version_label,
            "name": batch_name,
            "scope_note": scope_note,
            "item_count": len(items),
            "bucket": bucket,
            "priority": priority,
            "items": items,
        }
        batches.append(batch_payload)

    candidates.sort(key=lambda row: (row["priority"] != "high", row["part_name"], row["start"], row["round2_id"]))
    bucket_counts = Counter(row["bucket"] for row in candidates)
    priority_counts = Counter(row["priority"] for row in candidates)
    status_counts = Counter(row["current_status"] for row in candidates)

    manifest = {
        "version": args.version_label,
        "source_reviewed_master_json": str(args.reviewed_master_json),
        "candidate_count": len(candidates),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "current_status_counts": dict(sorted(status_counts.items())),
        "thresholds": {
            "autoaccepted_match_score_lt": args.auto_threshold,
            "part04_confirmed_match_score_lt": args.part04_threshold,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "candidates.json", {"manifest": manifest, "segments": candidates})
    write_tsv(args.output_dir / "candidates.tsv", candidates)

    batches_dir = args.output_dir / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    for batch in batches:
        write_json(batches_dir / f"{batch['name']}.json", batch)

    (args.output_dir / "README.md").write_text(build_readme(manifest, batches), encoding="utf-8")
    print(f"wrote round2 optimization pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
