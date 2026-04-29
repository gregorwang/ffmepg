from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PACKS = [
    {
        "name": "phase_b_delivery_v10",
        "path": Path("scratch/phase_b_delivery_v10"),
        "coverage_label": "part01/part02 正式阶段包",
        "quality_label": "phase-b-accepted",
        "part_status": {
            "part01": "phase-b-accepted",
            "part02": "phase-b-accepted",
        },
    },
    {
        "name": "phase_b_part03_seed_expansion_delivery_v1",
        "path": Path("scratch/phase_b_part03_seed_expansion_delivery_v1"),
        "coverage_label": "part03 局部连续候选包",
        "quality_label": "phase-b-partial",
        "part_status": {
            "part03": "phase-b-partial",
        },
    },
    {
        "name": "phase_b_part04_partial_delivery_v5",
        "path": Path("scratch/phase_b_part04_partial_delivery_v5"),
        "coverage_label": "part04 filter-mapped 局部候选包",
        "quality_label": "phase-b-partial",
        "part_status": {
            "part04": "phase-b-partial",
        },
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a master Phase B delivery index from accepted and partial delivery packs."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("scratch/phase_b_master_delivery_v1"),
    )
    parser.add_argument(
        "--version-label",
        type=str,
        default="phase-b-master-delivery-v1",
    )
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "global_segment_id",
        "part_name",
        "quality_label",
        "source_pack",
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
    lines = [
        "# Ghost Yotei Phase B Master Delivery",
        "",
        "## Scope",
        "",
        "- This index merges the accepted `part01/part02` Phase B pack with the current best `part03` and `part04` partial packs.",
        "- `part01` and `part02` are treated as accepted local bilingual deliverables.",
        "- `part03` is treated as a partial local bilingual deliverable based on the current best remap + seed expansion path.",
        "- `part04` is treated as a partial local bilingual deliverable based on filter-mapped trial alignment; it is weaker than `part01/part02` and narrower in coverage.",
        "",
        "## Aggregate Stats",
        "",
        f"- Total segments: `{manifest['total_segment_count']}`",
        f"- Parts covered: `{', '.join(manifest['parts_covered'])}`",
        "",
        "## Quality Labels",
        "",
        "- `phase-b-accepted`: accepted local bilingual deliverable",
        "- `phase-b-partial`: useful local bilingual deliverable, but still not full-part completion",
        "",
        "## Files",
        "",
        "- `manifest.json`: merged metadata and per-pack stats",
        "- `all_segments.json`: merged machine-readable segments",
        "- `all_segments.tsv`: merged tabular export",
        "- `packs.json`: source pack references and labels",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    merged_rows: list[dict[str, Any]] = []
    pack_summaries: list[dict[str, Any]] = []
    global_index = 1

    for pack in PACKS:
        manifest_path = pack["path"] / "manifest.json"
        all_segments_path = pack["path"] / "all_segments.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        all_segments = json.loads(all_segments_path.read_text(encoding="utf-8"))
        segments = list(all_segments.get("segments") or [])

        for row in segments:
            part_short = row["part_name"].replace("ghost-yotei-", "")
            merged_rows.append(
                {
                    "global_segment_id": f"mseg_{global_index:05d}",
                    "part_name": row["part_name"],
                    "quality_label": pack["part_status"].get(part_short, pack["quality_label"]),
                    "source_pack": pack["name"],
                    "source_clip": row["source_clip"],
                    "start": row["start"],
                    "end": row["end"],
                    "duration": row["duration"],
                    "match_score": row["match_score"],
                    "selection_mode": row["selection_mode"],
                    "alignment_type": row["alignment_type"],
                    "english_cue_ids": list(row["english_cue_ids"]),
                    "chinese_cue_ids": list(row["chinese_cue_ids"]),
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                }
            )
            global_index += 1

        pack_summaries.append(
            {
                "name": pack["name"],
                "path": str(pack["path"]),
                "coverage_label": pack["coverage_label"],
                "quality_label": pack["quality_label"],
                "parts_covered": manifest["parts_covered"],
                "total_segment_count": manifest["total_segment_count"],
            }
        )

    merged_rows.sort(key=lambda row: (row["part_name"], row["start"], row["end"], row["global_segment_id"]))
    quality_counts = Counter(row["quality_label"] for row in merged_rows)
    part_counts = Counter(row["part_name"].replace("ghost-yotei-", "") for row in merged_rows)
    manifest = {
        "version": args.version_label,
        "total_segment_count": len(merged_rows),
        "parts_covered": sorted(part_counts),
        "quality_counts": dict(sorted(quality_counts.items())),
        "part_counts": dict(sorted(part_counts.items())),
        "source_pack_count": len(pack_summaries),
    }

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "manifest.json", manifest)
    write_json(output_dir / "packs.json", {"packs": pack_summaries})
    write_json(output_dir / "all_segments.json", {"segments": merged_rows, "manifest": manifest})
    write_tsv(output_dir / "all_segments.tsv", merged_rows)
    write_readme(output_dir / "README.md", manifest)
    print(f"wrote master delivery -> {output_dir}")


if __name__ == "__main__":
    main()
