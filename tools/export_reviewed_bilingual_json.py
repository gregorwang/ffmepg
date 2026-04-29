from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_INCLUDE_STATUSES = ["auto-accepted", "confirmed", "revised", "split-derived"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export final bilingual JSON files from a reviewed Phase B master package."
    )
    parser.add_argument("--reviewed-master-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--include-status",
        action="append",
        default=[],
        help="Review status to include. Can be passed multiple times. Defaults to auto-accepted/confirmed/revised/split-derived.",
    )
    parser.add_argument(
        "--version-label",
        type=str,
        default="phase-b-reviewed-final-v1",
        help="Version label written into the final export manifest.",
    )
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "segment_id",
        "part_name",
        "start",
        "end",
        "duration",
        "review_status",
        "quality_label",
        "match_score",
        "selection_mode",
        "alignment_type",
        "source_clip",
        "english_text",
        "chinese_text",
        "english_cue_ids",
        "chinese_cue_ids",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "segment_id": row["segment_id"],
                    "part_name": row["part_name"],
                    "start": row["start"],
                    "end": row["end"],
                    "duration": row["duration"],
                    "review_status": row["review_status"],
                    "quality_label": row["quality_label"],
                    "match_score": row["match_score"],
                    "selection_mode": row["selection_mode"],
                    "alignment_type": row["alignment_type"],
                    "source_clip": row["source_clip"],
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                    "english_cue_ids": ",".join(row.get("english_cue_ids") or []),
                    "chinese_cue_ids": ",".join(row.get("chinese_cue_ids") or []),
                }
            )


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Phase B Reviewed Final Export",
        "",
        f"- Version: `{manifest['version']}`",
        f"- Source reviewed master: `{manifest['source_reviewed_master_json']}`",
        f"- Included review statuses: `{', '.join(manifest['included_statuses'])}`",
        f"- Total exported segments: `{manifest['total_segment_count']}`",
        "",
        "## Notes",
        "",
        "- This export is the final bilingual JSON view derived from the reviewed master baseline.",
        "- Rows marked `needs-review`, `excluded`, or `superseded-by-split` are intentionally omitted.",
        "",
        "## Files",
        "",
        "- `manifest.json`: aggregate export statistics",
        "- `all_segments.json`: merged final bilingual rows",
        "- `all_segments.tsv`: tabular review-friendly export",
        "- `<part>/<part>.bilingual.json`: per-part machine-readable export",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def part_short_name(part_name: str) -> str:
    return part_name.replace("ghost-yotei-", "")


def to_final_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "segment_id": f"final_{index:04d}",
        "source_segment_id": row["global_segment_id"],
        "part_name": row["part_name"],
        "start": row["start"],
        "end": row["end"],
        "duration": row["duration"],
        "review_status": row["review_status"],
        "quality_label": row["quality_label"],
        "match_score": row["match_score"],
        "selection_mode": row["selection_mode"],
        "alignment_type": row["alignment_type"],
        "source_clip": row["source_clip"],
        "english_cue_ids": list(row.get("english_cue_ids") or []),
        "chinese_cue_ids": list(row.get("chinese_cue_ids") or []),
        "english_text": row["english_text"],
        "chinese_text": row["chinese_text"],
        "review_notes": row.get("review_notes", ""),
    }


def main() -> None:
    args = parse_args()
    payload = json.loads(args.reviewed_master_json.read_text(encoding="utf-8"))
    include_statuses = args.include_status or list(DEFAULT_INCLUDE_STATUSES)
    included_set = set(include_statuses)

    source_rows = list(payload.get("segments") or [])
    filtered_rows = [row for row in source_rows if row.get("review_status") in included_set]
    filtered_rows.sort(key=lambda row: (row["part_name"], row["start"], row["end"], row["global_segment_id"]))
    final_rows = [to_final_row(row, index) for index, row in enumerate(filtered_rows, start=1)]

    part_groups: dict[str, list[dict[str, Any]]] = {}
    for row in final_rows:
        part_groups.setdefault(row["part_name"], []).append(row)

    review_status_counts = Counter(row["review_status"] for row in final_rows)
    part_counts = Counter(part_short_name(row["part_name"]) for row in final_rows)
    manifest = {
        "version": args.version_label,
        "source_reviewed_master_json": str(args.reviewed_master_json),
        "included_statuses": include_statuses,
        "total_segment_count": len(final_rows),
        "parts_covered": sorted(part_counts),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "part_counts": dict(sorted(part_counts.items())),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "all_segments.json", {"segments": final_rows, "manifest": manifest})
    write_tsv(args.output_dir / "all_segments.tsv", final_rows)
    write_readme(args.output_dir / "README.md", manifest)

    for part_name, rows in sorted(part_groups.items()):
        short_name = part_short_name(part_name)
        write_json(
            args.output_dir / short_name / f"{short_name}.bilingual.json",
            {
                "version": args.version_label,
                "part_name": part_name,
                "short_name": short_name,
                "segment_count": len(rows),
                "segments": rows,
            },
        )
        write_tsv(args.output_dir / short_name / f"{short_name}.bilingual.tsv", rows)

    print(f"wrote reviewed final export -> {args.output_dir}")


if __name__ == "__main__":
    main()
