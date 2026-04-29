from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a delivery-oriented package from Phase B cue-level bilingual alignment output."
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        required=True,
        help="Phase B cue-level alignment JSON.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for the exported delivery pack.",
    )
    parser.add_argument(
        "--review-status",
        type=str,
        default="accepted-phase-b-v10",
        help="Review status label stamped onto exported segments.",
    )
    parser.add_argument(
        "--package-title",
        type=str,
        default="Ghost Yotei Phase B Delivery Pack",
        help="README title for the exported pack.",
    )
    parser.add_argument(
        "--scope-note",
        action="append",
        default=[],
        help="Extra note line appended to the README scope section. Can be passed multiple times.",
    )
    return parser.parse_args()


def part_short_name(part_name: str) -> str:
    return part_name.replace("ghost-yotei-", "")


def to_delivery_row(row: dict[str, Any], index: int, review_status: str) -> dict[str, Any]:
    return {
        "segment_id": f"seg_{index:04d}",
        "part_name": row["part_name"],
        "cluster_id": row["cluster_id"],
        "source_clip": row["source_clip"],
        "start": row["start"],
        "end": row["end"],
        "duration": round(float(row["end"]) - float(row["start"]), 3),
        "match_score": row["match_score"],
        "selection_mode": row["selection_mode"],
        "alignment_type": row["alignment_type"],
        "english_cue_ids": list(row.get("english_cue_ids") or []),
        "chinese_cue_ids": list(row.get("chinese_cue_ids") or []),
        "english_text": row["english_text"],
        "chinese_text": row["chinese_text"],
        "review_status": review_status,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "segment_id",
        "part_name",
        "cluster_id",
        "source_clip",
        "start",
        "end",
        "duration",
        "match_score",
        "selection_mode",
        "alignment_type",
        "english_cue_ids",
        "chinese_cue_ids",
        "english_text",
        "chinese_text",
        "review_status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "english_cue_ids": ",".join(row["english_cue_ids"]),
                    "chinese_cue_ids": ",".join(row["chinese_cue_ids"]),
                }
            )


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    scope_notes = list(manifest.get("scope_notes") or [])
    if not scope_notes:
        scope_notes = [
            "This pack represents the Phase B local bilingual deliverable for `part01` and `part02`.",
            f"`review_status={manifest['review_status']}` marks the current acceptance status for this pack.",
            "`strict_review` artifacts preserve manual decisions and compression traces; they are not open bug lists.",
            "This pack does not claim full-series bilingual timeline completion, especially not for `part03` or all of `part04`.",
        ]
    lines = [
        f"# {manifest['package_title']}",
        "",
        f"- Source version: `{manifest['source_version']}`",
        f"- Alignment strategy: `{manifest['alignment_strategy']}`",
        f"- Total accepted segments: `{manifest['total_segment_count']}`",
        f"- Parts covered: `{', '.join(manifest['parts_covered'])}`",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in scope_notes)
    lines.extend(
        [
            "",
            "## Files",
        "",
        "- `manifest.json`: package metadata and statistics",
        "- `all_segments.json`: all accepted segments in one file",
        "- `all_segments.tsv`: tabular export for quick review",
        "- `<part>/<part>.delivery.json` and `<part>/<part>.delivery.tsv`: part-scoped exports",
        "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    flat_rows = list(payload.get("flat_candidates") or payload.get("segments") or [])
    delivery_rows = [to_delivery_row(row, index, args.review_status) for index, row in enumerate(flat_rows, start=1)]

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    part_groups: dict[str, list[dict[str, Any]]] = {}
    for row in delivery_rows:
        part_groups.setdefault(row["part_name"], []).append(row)

    selection_counter = Counter(row["selection_mode"] for row in delivery_rows)
    alignment_counter = Counter(row["alignment_type"] for row in delivery_rows)
    manifest = {
        "source_json": str(args.input_json),
        "source_version": payload.get("version"),
        "alignment_strategy": payload.get("alignment_strategy"),
        "total_segment_count": len(delivery_rows),
        "parts_covered": [part_short_name(name) for name in sorted(part_groups)],
        "review_status": args.review_status,
        "package_title": args.package_title,
        "scope_notes": args.scope_note,
        "selection_mode_counts": dict(sorted(selection_counter.items())),
        "alignment_type_counts": dict(sorted(alignment_counter.items())),
        "part_stats": [
            {
                "part_name": name,
                "short_name": part_short_name(name),
                "segment_count": len(rows),
                "start_min": min(row["start"] for row in rows),
                "end_max": max(row["end"] for row in rows),
            }
            for name, rows in sorted(part_groups.items())
        ],
    }

    write_json(output_dir / "manifest.json", manifest)
    write_json(output_dir / "all_segments.json", {"segments": delivery_rows, "manifest": manifest})
    write_tsv(output_dir / "all_segments.tsv", delivery_rows)
    write_readme(output_dir / "README.md", manifest)

    for part_name, rows in sorted(part_groups.items()):
        short_name = part_short_name(part_name)
        write_json(
            output_dir / short_name / f"{short_name}.delivery.json",
            {
                "part_name": part_name,
                "short_name": short_name,
                "segment_count": len(rows),
                "segments": rows,
            },
        )
        write_tsv(output_dir / short_name / f"{short_name}.delivery.tsv", rows)

    print(f"wrote delivery pack -> {output_dir}")


if __name__ == "__main__":
    main()
