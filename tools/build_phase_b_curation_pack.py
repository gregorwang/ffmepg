from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


MANUAL_SELECTION_MODES = {
    "manual-override",
    "manual-replacement",
    "anchor-fallback",
    "manual-accepted-compression",
    "manual-text-cleanup",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a manual curation pack from a Phase B master delivery package."
    )
    parser.add_argument("--master-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--accepted-low-score-threshold", type=float, default=0.75)
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "curation_id",
        "priority",
        "reason_tags",
        "part_name",
        "quality_label",
        "selection_mode",
        "source_pack",
        "source_clip",
        "start",
        "end",
        "duration",
        "match_score",
        "english_cue_ids",
        "chinese_cue_ids",
        "english_text",
        "chinese_text",
        "global_segment_id",
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
                    "reason_tags": ",".join(row["reason_tags"]),
                }
            )


def classify_segment(segment: dict[str, Any], accepted_low_score_threshold: float) -> tuple[bool, list[str], str]:
    reason_tags: list[str] = []
    quality_label = str(segment["quality_label"])
    selection_mode = str(segment["selection_mode"])
    match_score = float(segment["match_score"])

    if quality_label == "phase-b-partial":
        reason_tags.append("partial-segment")
    if selection_mode in MANUAL_SELECTION_MODES:
        reason_tags.append("manual-decision-trace")
    if quality_label == "phase-b-accepted" and match_score < accepted_low_score_threshold:
        reason_tags.append("accepted-low-score")

    if not reason_tags:
        return False, [], "skip"

    if "manual-decision-trace" in reason_tags and quality_label == "phase-b-accepted":
        priority = "high"
    elif quality_label == "phase-b-partial" and selection_mode in {"manual-accepted-compression", "manual-text-cleanup"}:
        priority = "high"
    elif quality_label == "phase-b-partial" and match_score < 0.72:
        priority = "high"
    elif quality_label == "phase-b-partial":
        priority = "medium"
    else:
        priority = "medium"
    return True, reason_tags, priority


def build_readme(manifest: dict[str, Any]) -> str:
    lines = [
        "# Ghost Yotei Phase B Curation Pack",
        "",
        "## Purpose",
        "",
        "- This pack is a manual-review surface, not a final delivery pack.",
        "- It extracts the most valuable segments for human curation from the current master delivery.",
        "- It prioritizes partial segments, manual engineering decisions, and accepted-but-borderline rows.",
        "",
        "## Stats",
        "",
        f"- Source master: `{manifest['source_master_version']}`",
        f"- Included segments: `{manifest['total_segment_count']}`",
        f"- High priority: `{manifest['priority_counts'].get('high', 0)}`",
        f"- Medium priority: `{manifest['priority_counts'].get('medium', 0)}`",
        "",
        "## Files",
        "",
        "- `manifest.json`: pack metadata and counts",
        "- `curation_segments.json`: machine-readable curation list",
        "- `curation_segments.tsv`: full review table",
        "- `shortlist_high_priority.tsv`: compact high-priority subset",
        "- `part_summaries.json`: per-part curation summary",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    master_manifest = json.loads((args.master_dir / "manifest.json").read_text(encoding="utf-8"))
    all_segments_payload = json.loads((args.master_dir / "all_segments.json").read_text(encoding="utf-8"))
    segments = list(all_segments_payload.get("segments") or [])

    curated_rows: list[dict[str, Any]] = []
    priority_counter: Counter[str] = Counter()
    by_part: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for index, segment in enumerate(segments, start=1):
        keep, reason_tags, priority = classify_segment(segment, args.accepted_low_score_threshold)
        if not keep:
            continue
        row = {
            "curation_id": f"cur_{index:04d}",
            "priority": priority,
            "reason_tags": reason_tags,
            "part_name": segment["part_name"],
            "quality_label": segment["quality_label"],
            "selection_mode": segment["selection_mode"],
            "source_pack": segment["source_pack"],
            "source_clip": segment["source_clip"],
            "start": segment["start"],
            "end": segment["end"],
            "duration": segment["duration"],
            "match_score": segment["match_score"],
            "english_cue_ids": list(segment["english_cue_ids"]),
            "chinese_cue_ids": list(segment["chinese_cue_ids"]),
            "english_text": segment["english_text"],
            "chinese_text": segment["chinese_text"],
            "global_segment_id": segment["global_segment_id"],
        }
        curated_rows.append(row)
        priority_counter[priority] += 1
        by_part[row["part_name"]].append(row)

    curated_rows.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(row["priority"], 9),
            row["part_name"],
            row["start"],
            row["global_segment_id"],
        )
    )

    part_summaries = []
    for part_name, rows in sorted(by_part.items()):
        part_summaries.append(
            {
                "part_name": part_name,
                "segment_count": len(rows),
                "priority_counts": dict(sorted(Counter(row["priority"] for row in rows).items())),
                "selection_mode_counts": dict(sorted(Counter(row["selection_mode"] for row in rows).items())),
                "reason_tag_counts": dict(sorted(Counter(tag for row in rows for tag in row["reason_tags"]).items())),
            }
        )

    manifest = {
        "version": "phase-b-curation-pack-v1",
        "source_master_dir": str(args.master_dir),
        "source_master_version": master_manifest["version"],
        "source_master_total_segment_count": master_manifest["total_segment_count"],
        "total_segment_count": len(curated_rows),
        "priority_counts": dict(sorted(priority_counter.items())),
        "part_count": len(part_summaries),
        "parts_covered": [item["part_name"].replace("ghost-yotei-", "") for item in part_summaries],
    }

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "manifest.json", manifest)
    write_json(output_dir / "curation_segments.json", {"segments": curated_rows, "manifest": manifest})
    write_tsv(output_dir / "curation_segments.tsv", curated_rows)
    write_tsv(output_dir / "shortlist_high_priority.tsv", [row for row in curated_rows if row["priority"] == "high"])
    write_json(output_dir / "part_summaries.json", {"parts": part_summaries})
    (output_dir / "README.md").write_text(build_readme(manifest), encoding="utf-8")
    print(f"wrote curation pack -> {output_dir}")


if __name__ == "__main__":
    main()

