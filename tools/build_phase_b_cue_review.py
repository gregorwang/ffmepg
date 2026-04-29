from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate strict/actionable review TSVs for cue-level bilingual alignment outputs."
    )
    parser.add_argument(
        "--input-json",
        type=Path,
        required=True,
        help="Cue-level alignment JSON payload.",
    )
    parser.add_argument(
        "--strict-output",
        type=Path,
        help="Strict review TSV path. Defaults to <input_stem>_strict_review.tsv",
    )
    parser.add_argument(
        "--actionable-output",
        type=Path,
        help="Actionable review TSV path. Defaults to <input_stem>_actionable_review.tsv",
    )
    return parser.parse_args()


def infer_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    selection_mode = str(row.get("selection_mode") or "")
    english_ids = list(row.get("english_cue_ids") or [])
    chinese_ids = list(row.get("chinese_cue_ids") or [])

    if selection_mode in {"anchor-fallback", "manual-override", "manual-replacement"}:
        reasons.append(selection_mode)
    if len(english_ids) > len(chinese_ids):
        reasons.append("structural_compression")
    return reasons


def is_actionable(row: dict[str, Any], reasons: list[str]) -> bool:
    selection_mode = str(row.get("selection_mode") or "")
    has_structural = "structural_compression" in reasons
    if not has_structural:
        return False
    # Manual replacements are explicit accept/keep decisions, not active work items.
    if selection_mode == "manual-replacement":
        return False
    return True


def build_review_rows(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    strict_rows: list[dict[str, Any]] = []
    actionable_rows: list[dict[str, Any]] = []
    for row in payload.get("flat_candidates") or []:
        reasons = infer_reasons(row)
        if not reasons:
            continue
        review_row = {
            "part_name": row.get("part_name"),
            "cluster_id": row.get("cluster_id"),
            "match_score": row.get("match_score"),
            "selection_mode": row.get("selection_mode"),
            "alignment_type": row.get("alignment_type"),
            "english_cue_ids": ",".join(row.get("english_cue_ids") or []),
            "chinese_cue_ids": ",".join(row.get("chinese_cue_ids") or []),
            "reasons": ",".join(reasons),
            "english_text": row.get("english_text"),
            "chinese_text": row.get("chinese_text"),
        }
        strict_rows.append(review_row)
        if is_actionable(row, reasons):
            actionable_rows.append(review_row)

    strict_rows.sort(key=lambda item: (item["part_name"], item["cluster_id"], str(item["english_cue_ids"])))
    actionable_rows.sort(
        key=lambda item: (item["part_name"], item["cluster_id"], str(item["english_cue_ids"]))
    )
    return strict_rows, actionable_rows


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "part_name",
        "cluster_id",
        "match_score",
        "selection_mode",
        "alignment_type",
        "english_cue_ids",
        "chinese_cue_ids",
        "reasons",
        "english_text",
        "chinese_text",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    input_stem = args.input_json.with_suffix("")
    strict_output = args.strict_output or input_stem.with_name(f"{input_stem.name}_strict_review.tsv")
    actionable_output = args.actionable_output or input_stem.with_name(
        f"{input_stem.name}_actionable_review.tsv"
    )

    strict_rows, actionable_rows = build_review_rows(payload)
    write_tsv(strict_output, strict_rows)
    write_tsv(actionable_output, actionable_rows)

    print(f"strict={len(strict_rows)} -> {strict_output}")
    print(f"actionable={len(actionable_rows)} -> {actionable_output}")


if __name__ == "__main__":
    main()
