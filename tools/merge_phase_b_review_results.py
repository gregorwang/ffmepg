from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_REVISED_FIELDS = {
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
    "quality_label",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge Phase B manual review patch files back into a reviewed master package."
    )
    parser.add_argument("--master-json", type=Path, required=True, help="phase_b_master_delivery_v9/all_segments.json")
    parser.add_argument("--curation-json", type=Path, required=True, help="phase_b_curation_pack_v1/curation_segments.json")
    parser.add_argument(
        "--patch-json",
        type=Path,
        action="append",
        default=[],
        help="Review patch template/result JSON. Can be passed multiple times.",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for reviewed master output.")
    parser.add_argument(
        "--version-label",
        type=str,
        default="phase-b-master-reviewed-v1",
        help="Version label for the reviewed master manifest.",
    )
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "global_segment_id",
        "part_name",
        "quality_label",
        "review_status",
        "curation_priority",
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
        "review_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "global_segment_id": row["global_segment_id"],
                    "part_name": row["part_name"],
                    "quality_label": row["quality_label"],
                    "review_status": row["review_status"],
                    "curation_priority": row.get("curation_priority"),
                    "source_pack": row["source_pack"],
                    "source_clip": row["source_clip"],
                    "start": row["start"],
                    "end": row["end"],
                    "duration": row["duration"],
                    "match_score": row["match_score"],
                    "selection_mode": row["selection_mode"],
                    "alignment_type": row["alignment_type"],
                    "english_cue_ids": ",".join(row.get("english_cue_ids") or []),
                    "chinese_cue_ids": ",".join(row.get("chinese_cue_ids") or []),
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                    "review_notes": row.get("review_notes", ""),
                }
            )


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Phase B Reviewed Master",
        "",
        f"- Version: `{manifest['version']}`",
        f"- Source master: `{manifest['source_master_json']}`",
        f"- Source curation pack: `{manifest['source_curation_json']}`",
        f"- Patch file count: `{len(manifest['patch_files_applied'])}`",
        f"- Total segments: `{manifest['total_segment_count']}`",
        "",
        "## Review Statuses",
        "",
        "- `auto-accepted`: accepted by automatic baseline and not currently in curation scope",
        "- `needs-review`: still pending manual review",
        "- `confirmed`: manually reviewed and confirmed",
        "- `revised`: manually reviewed and edited in-place",
        "- `excluded`: manually removed from final deliverable",
        "- `superseded-by-split`: original row replaced by split-derived rows",
        "- `split-derived`: created from a manual split decision",
        "",
        "## Files",
        "",
        "- `all_segments.json`: reviewed master rows with review metadata",
        "- `all_segments.tsv`: tabular export",
        "- `manifest.json`: aggregate status counts",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_curation_lookup(curation_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in curation_payload.get("segments") or []:
        lookup[row["global_segment_id"]] = row
    return lookup


def build_baseline_row(row: dict[str, Any], curation_row: dict[str, Any] | None) -> dict[str, Any]:
    reviewed = dict(row)
    reviewed["review_status"] = (
        "needs-review"
        if curation_row is not None or row["quality_label"] != "phase-b-accepted"
        else "auto-accepted"
    )
    reviewed["review_notes"] = ""
    reviewed["review_sources"] = []
    reviewed["curation_id"] = curation_row.get("curation_id") if curation_row else None
    reviewed["curation_priority"] = curation_row.get("priority") if curation_row else None
    reviewed["curation_reason_tags"] = list(curation_row.get("reason_tags") or []) if curation_row else []
    return reviewed


def apply_revised_fields(target: dict[str, Any], revised_fields: dict[str, Any], patch_ref: str, notes: str) -> None:
    for key, value in revised_fields.items():
        if key not in ALLOWED_REVISED_FIELDS:
            continue
        target[key] = value
    if "start" in revised_fields and "end" in revised_fields and "duration" not in revised_fields:
        target["duration"] = round(float(target["end"]) - float(target["start"]), 3)
    target["review_status"] = "revised"
    target["review_notes"] = notes
    target["review_sources"] = list(target.get("review_sources") or []) + [patch_ref]


def build_split_row(
    original: dict[str, Any],
    split_payload: dict[str, Any],
    split_index: int,
    patch_ref: str,
    notes: str,
) -> dict[str, Any]:
    row = dict(original)
    suffix = split_payload.get("segment_suffix") or f"s{split_index:02d}"
    row["global_segment_id"] = f"{original['global_segment_id']}__{suffix}"
    row["parent_segment_id"] = original["global_segment_id"]
    row["review_status"] = "split-derived"
    row["review_notes"] = notes
    row["review_sources"] = [patch_ref]
    row["selection_mode"] = split_payload.get("selection_mode", "manual-review-split")
    for key, value in split_payload.items():
        if key in {"segment_suffix", "review_status", "review_notes", "review_sources"}:
            continue
        row[key] = value
    if "start" in row and "end" in row:
        row["duration"] = round(float(row["end"]) - float(row["start"]), 3)
    return row


def main() -> None:
    args = parse_args()
    master_payload = load_json(args.master_json)
    curation_payload = load_json(args.curation_json)

    curation_lookup = build_curation_lookup(curation_payload)
    base_rows = [build_baseline_row(row, curation_lookup.get(row["global_segment_id"])) for row in master_payload["segments"]]
    reviewed_by_id = {row["global_segment_id"]: row for row in base_rows}
    split_rows: list[dict[str, Any]] = []
    patch_files_applied: list[str] = []

    for patch_path in args.patch_json:
        patch_payload = load_json(patch_path)
        patch_files_applied.append(str(patch_path))
        round_name = patch_payload.get("manifest", {}).get("round_name", patch_path.stem)
        for item in patch_payload.get("items") or []:
            decision = item.get("decision", "pending")
            if decision == "pending":
                continue
            global_segment_id = item["global_segment_id"]
            if global_segment_id not in reviewed_by_id:
                raise KeyError(f"review patch references missing segment: {global_segment_id}")
            target = reviewed_by_id[global_segment_id]
            patch_ref = f"{round_name}:{item.get('patch_id', global_segment_id)}"
            notes = item.get("notes", "")

            if decision == "confirmed":
                target["review_status"] = "confirmed"
                target["review_notes"] = notes
                target["review_sources"] = list(target.get("review_sources") or []) + [patch_ref]
            elif decision == "revised":
                apply_revised_fields(target, item.get("revised_fields") or {}, patch_ref, notes)
            elif decision == "excluded":
                target["review_status"] = "excluded"
                target["review_notes"] = notes
                target["review_sources"] = list(target.get("review_sources") or []) + [patch_ref]
            elif decision == "split":
                target["review_status"] = "superseded-by-split"
                target["review_notes"] = notes
                target["review_sources"] = list(target.get("review_sources") or []) + [patch_ref]
                split_payloads = list(item.get("split_segments") or [])
                for split_index, split_payload in enumerate(split_payloads, start=1):
                    split_rows.append(build_split_row(target, split_payload, split_index, patch_ref, notes))
            else:
                raise ValueError(f"unsupported review decision: {decision}")

    merged_rows = list(reviewed_by_id.values()) + split_rows
    merged_rows.sort(key=lambda row: (row["part_name"], row["start"], row["end"], row["global_segment_id"]))

    review_status_counts = Counter(row["review_status"] for row in merged_rows)
    quality_counts = Counter(row["quality_label"] for row in merged_rows)
    part_counts = Counter(row["part_name"].replace("ghost-yotei-", "") for row in merged_rows)
    manifest = {
        "version": args.version_label,
        "source_master_json": str(args.master_json),
        "source_curation_json": str(args.curation_json),
        "patch_files_applied": patch_files_applied,
        "total_segment_count": len(merged_rows),
        "parts_covered": sorted(part_counts),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "quality_counts": dict(sorted(quality_counts.items())),
        "part_counts": dict(sorted(part_counts.items())),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "all_segments.json", {"segments": merged_rows, "manifest": manifest})
    write_tsv(args.output_dir / "all_segments.tsv", merged_rows)
    write_readme(args.output_dir / "README.md", manifest)
    print(f"wrote reviewed master -> {args.output_dir}")


if __name__ == "__main__":
    main()
