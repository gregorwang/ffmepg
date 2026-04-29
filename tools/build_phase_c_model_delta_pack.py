from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_BASE_JSON = Path("scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2/all_segments.json")
DEFAULT_APPLIED_JSON = Path("scratch/phase_c_model_applied_v1/all_segments.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_model_delta_pack_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a delta pack between base Phase C output and model-applied output.")
    parser.add_argument("--base-json", type=Path, default=DEFAULT_BASE_JSON)
    parser.add_argument("--applied-json", type=Path, default=DEFAULT_APPLIED_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_payload(path: Path) -> dict[str, Any]:
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


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("part_name") or ""), str(row.get("english_cue_id") or "")


def text_changed(base_row: dict[str, Any], applied_row: dict[str, Any]) -> bool:
    return str(base_row.get("chinese_text") or "") != str(applied_row.get("chinese_text") or "")


def field_changed(base_row: dict[str, Any], applied_row: dict[str, Any], field: str) -> bool:
    return (base_row.get(field) or "") != (applied_row.get(field) or "")


def classify_change(base_row: dict[str, Any], applied_row: dict[str, Any]) -> str:
    base_status = str(base_row.get("status") or "")
    applied_status = str(applied_row.get("status") or "")
    base_text = str(base_row.get("chinese_text") or "")
    applied_text = str(applied_row.get("chinese_text") or "")

    if base_status != "unmatched" and applied_status == "unmatched":
        return "cleared-to-unmatched"
    if base_status == "unmatched" and applied_status != "unmatched" and applied_text:
        return "filled-from-unmatched"
    if base_text != applied_text and base_text and applied_text:
        return "replaced-text"
    if base_status != applied_status:
        return "status-only-change"
    return "metadata-change"


def main() -> None:
    args = parse_args()
    base_payload = load_payload(args.base_json)
    applied_payload = load_payload(args.applied_json)
    base_rows = list(base_payload.get("segments") or [])
    applied_rows = list(applied_payload.get("segments") or [])

    base_by_key = {row_key(row): row for row in base_rows}
    applied_by_key = {row_key(row): row for row in applied_rows}
    all_keys = sorted(set(base_by_key.keys()) | set(applied_by_key.keys()))

    changed_rows: list[dict[str, Any]] = []
    unchanged_count = 0
    missing_in_base = 0
    missing_in_applied = 0
    change_type_counts: Counter[str] = Counter()
    status_transition_counts: Counter[str] = Counter()
    part_change_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for key in all_keys:
        base_row = base_by_key.get(key)
        applied_row = applied_by_key.get(key)
        if base_row is None:
            missing_in_base += 1
            continue
        if applied_row is None:
            missing_in_applied += 1
            continue

        changed = any(
            [
                field_changed(base_row, applied_row, "status"),
                field_changed(base_row, applied_row, "match_origin"),
                field_changed(base_row, applied_row, "match_score"),
                text_changed(base_row, applied_row),
                field_changed(base_row, applied_row, "source_clip"),
                field_changed(base_row, applied_row, "notes"),
            ]
        )
        if not changed:
            unchanged_count += 1
            continue

        change_type = classify_change(base_row, applied_row)
        transition = f"{base_row.get('status') or ''} -> {applied_row.get('status') or ''}"
        part_name = str(applied_row.get("part_name") or base_row.get("part_name") or "")

        change_type_counts[change_type] += 1
        status_transition_counts[transition] += 1
        part_change_counts[part_name][change_type] += 1

        changed_rows.append(
            {
                "part_name": part_name,
                "clip_name": str(applied_row.get("source_clip") or base_row.get("source_clip") or ""),
                "english_cue_id": str(applied_row.get("english_cue_id") or base_row.get("english_cue_id") or ""),
                "start": applied_row.get("start", base_row.get("start", "")),
                "end": applied_row.get("end", base_row.get("end", "")),
                "change_type": change_type,
                "status_before": str(base_row.get("status") or ""),
                "status_after": str(applied_row.get("status") or ""),
                "origin_before": str(base_row.get("match_origin") or ""),
                "origin_after": str(applied_row.get("match_origin") or ""),
                "english_text": str(applied_row.get("english_text") or base_row.get("english_text") or ""),
                "chinese_text_before": str(base_row.get("chinese_text") or ""),
                "chinese_text_after": str(applied_row.get("chinese_text") or ""),
                "notes_before": str(base_row.get("notes") or ""),
                "notes_after": str(applied_row.get("notes") or ""),
            }
        )

    changed_rows.sort(key=lambda row: (row["part_name"], float(row["start"] or 0), row["english_cue_id"]))

    part_summaries = []
    for part_name in sorted({*part_change_counts.keys(), *(str(row.get("part_name") or "") for row in applied_rows)}):
        part_rows = [row for row in changed_rows if row["part_name"] == part_name]
        part_summaries.append(
            {
                "part_name": part_name,
                "changed_row_count": len(part_rows),
                "change_type_counts": dict(sorted(part_change_counts.get(part_name, Counter()).items())),
            }
        )

    manifest = {
        "base_json": str(args.base_json),
        "applied_json": str(args.applied_json),
        "base_row_count": len(base_rows),
        "applied_row_count": len(applied_rows),
        "changed_row_count": len(changed_rows),
        "unchanged_row_count": unchanged_count,
        "missing_in_base": missing_in_base,
        "missing_in_applied": missing_in_applied,
        "change_type_counts": dict(sorted(change_type_counts.items())),
        "status_transition_counts": dict(sorted(status_transition_counts.items())),
        "parts": part_summaries,
    }

    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "changed_rows.json", {"manifest": manifest, "rows": changed_rows})
    write_tsv(
        args.output_dir / "changed_rows.tsv",
        changed_rows,
        [
            "part_name",
            "clip_name",
            "english_cue_id",
            "start",
            "end",
            "change_type",
            "status_before",
            "status_after",
            "origin_before",
            "origin_after",
            "english_text",
            "chinese_text_before",
            "chinese_text_after",
            "notes_before",
            "notes_after",
        ],
    )
    print(f"wrote phase c delta pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
