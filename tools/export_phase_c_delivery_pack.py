from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_PHASE_C_DIR = Path("scratch/phase_c_predecision_applied_v3_complete")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_delivery_pack_v1_complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a delivery-oriented package from a completed Phase C output.")
    parser.add_argument("--phase-c-dir", type=Path, default=DEFAULT_PHASE_C_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--package-title", type=str, default="Ghost Yotei Phase C Delivery Pack")
    parser.add_argument("--delta-dir", type=Path)
    parser.add_argument("--burnin-dir", type=Path)
    parser.add_argument("--handoff-json", type=Path)
    parser.add_argument("--scope-note", action="append", default=[])
    return parser.parse_args()


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


def part_short_name(part_name: str) -> str:
    return part_name.replace("ghost-yotei-", "")


def delivery_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment_id": row.get("segment_id", ""),
        "part_name": row.get("part_name", ""),
        "start": row.get("start", ""),
        "end": row.get("end", ""),
        "duration": row.get("duration", ""),
        "status": row.get("status", ""),
        "match_origin": row.get("match_origin", ""),
        "match_score": row.get("match_score", ""),
        "source_clip": row.get("source_clip", ""),
        "english_cue_id": row.get("english_cue_id", ""),
        "english_text": row.get("english_text", ""),
        "chinese_text": row.get("chinese_text", ""),
        "chinese_cue_ids": ",".join(row.get("chinese_cue_ids") or []),
        "notes": row.get("notes", ""),
    }


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    scope_notes = list(manifest.get("scope_notes") or [])
    if not scope_notes:
        scope_notes = [
            "This pack is the current complete Phase C deliverable after deterministic closure of the entire review pool.",
            "It is intentionally speed-biased and does not claim high-precision subtitle alignment for every English cue.",
            "Rows with `status=unmatched` are closed as no-match, not pending model work.",
        ]
    lines = [
        f"# {manifest['package_title']}",
        "",
        f"- Source version: `{manifest['source_version']}`",
        f"- Total cues: `{manifest['total_cue_count']}`",
        f"- Matched cues: `{manifest['matched_cue_count']}`",
        f"- Unmatched cues: `{manifest['unmatched_cue_count']}`",
        f"- Coverage ratio: `{manifest['coverage_ratio']}`",
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
            "- `all_segments.json` / `all_segments.tsv`: full Phase C deliverable view",
            "- `matched_segments.json` / `matched_segments.tsv`: only rows with current Chinese text",
            "- `unmatched_segments.json` / `unmatched_segments.tsv`: closed no-match rows",
            "- `<part>/<part>.delivery.json|tsv`: per-part exports",
            "",
        ]
    )
    if manifest.get("delta_dir"):
        lines.append(f"- Delta reference: `{manifest['delta_dir']}`")
    if manifest.get("burnin_dir"):
        lines.append(f"- Burn-in prep: `{manifest['burnin_dir']}`")
    if manifest.get("handoff_json"):
        lines.append(f"- Handoff summary: `{manifest['handoff_json']}`")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    payload = json.loads((args.phase_c_dir / "all_segments.json").read_text(encoding="utf-8"))
    source_manifest = dict(payload.get("manifest") or {})
    source_rows = list(payload.get("segments") or [])
    rows = [delivery_row(row) for row in source_rows]
    matched_rows = [row for row in rows if str(row.get("status") or "") != "unmatched"]
    unmatched_rows = [row for row in rows if str(row.get("status") or "") == "unmatched"]

    part_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        part_groups.setdefault(str(row["part_name"]), []).append(row)

    status_counts = Counter(str(row["status"]) for row in rows)
    part_stats = []
    for part_name, part_rows in sorted(part_groups.items()):
        matched_count = sum(1 for row in part_rows if str(row.get("status") or "") != "unmatched")
        part_stats.append(
            {
                "part_name": part_name,
                "short_name": part_short_name(part_name),
                "segment_count": len(part_rows),
                "matched_count": matched_count,
                "unmatched_count": len(part_rows) - matched_count,
                "coverage_ratio": round(matched_count / max(len(part_rows), 1), 4),
            }
        )

    manifest = {
        "package_title": args.package_title,
        "source_phase_c_dir": str(args.phase_c_dir),
        "source_version": source_manifest.get("version"),
        "total_cue_count": len(rows),
        "matched_cue_count": len(matched_rows),
        "unmatched_cue_count": len(unmatched_rows),
        "coverage_ratio": round(len(matched_rows) / max(len(rows), 1), 4),
        "status_counts": dict(sorted(status_counts.items())),
        "part_stats": part_stats,
        "delta_dir": str(args.delta_dir) if args.delta_dir else "",
        "burnin_dir": str(args.burnin_dir) if args.burnin_dir else "",
        "handoff_json": str(args.handoff_json) if args.handoff_json else "",
        "scope_notes": args.scope_note,
    }

    fieldnames = [
        "segment_id",
        "part_name",
        "start",
        "end",
        "duration",
        "status",
        "match_origin",
        "match_score",
        "source_clip",
        "english_cue_id",
        "english_text",
        "chinese_text",
        "chinese_cue_ids",
        "notes",
    ]

    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "all_segments.json", {"manifest": manifest, "segments": rows})
    write_tsv(args.output_dir / "all_segments.tsv", rows, fieldnames)
    write_json(args.output_dir / "matched_segments.json", {"manifest": manifest, "segments": matched_rows})
    write_tsv(args.output_dir / "matched_segments.tsv", matched_rows, fieldnames)
    write_json(args.output_dir / "unmatched_segments.json", {"manifest": manifest, "segments": unmatched_rows})
    write_tsv(args.output_dir / "unmatched_segments.tsv", unmatched_rows, fieldnames)
    write_readme(args.output_dir / "README.md", manifest)

    for part_name, part_rows in sorted(part_groups.items()):
        short_name = part_short_name(part_name)
        payload = {
            "part_name": part_name,
            "short_name": short_name,
            "segment_count": len(part_rows),
            "matched_count": sum(1 for row in part_rows if str(row.get("status") or "") != "unmatched"),
            "segments": part_rows,
        }
        write_json(args.output_dir / short_name / f"{short_name}.delivery.json", payload)
        write_tsv(args.output_dir / short_name / f"{short_name}.delivery.tsv", part_rows, fieldnames)

    print(f"wrote phase c delivery pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
