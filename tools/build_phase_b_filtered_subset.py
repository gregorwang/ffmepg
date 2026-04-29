from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_phase_b_cue_local_align import write_tsv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a filtered subset from a Phase B flat-candidate JSON."
    )
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-tsv", type=Path, required=True)
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--exclude-structural-compression", action="store_true")
    parser.add_argument(
        "--include-english-cue-ids",
        action="append",
        default=[],
        help="Comma-separated english cue ids to force-include, even if they would otherwise be filtered out.",
    )
    parser.add_argument(
        "--include-selection-mode",
        type=str,
        default="manual-accepted-compression",
        help="Selection mode assigned to force-included rows.",
    )
    return parser.parse_args()


def keep_row(row: dict[str, Any], min_score: float, exclude_structural: bool) -> bool:
    if float(row.get("match_score") or 0.0) < min_score:
        return False
    if exclude_structural and len(list(row.get("english_cue_ids") or [])) > len(list(row.get("chinese_cue_ids") or [])):
        return False
    return True


def parse_include_sets(raw_items: list[str]) -> set[tuple[str, ...]]:
    outputs: set[tuple[str, ...]] = set()
    for item in raw_items:
        cue_ids = tuple(part.strip() for part in item.split(",") if part.strip())
        if cue_ids:
            outputs.add(cue_ids)
    return outputs


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    include_sets = parse_include_sets(args.include_english_cue_ids)
    rows = [
        row
        for row in (payload.get("flat_candidates") or [])
        if keep_row(
            row=row,
            min_score=args.min_score,
            exclude_structural=args.exclude_structural_compression,
        )
    ]
    seen_keys = {tuple(row.get("english_cue_ids") or []) for row in rows}
    for row in payload.get("flat_candidates") or []:
        key = tuple(row.get("english_cue_ids") or [])
        if key not in include_sets or key in seen_keys:
            continue
        forced = dict(row)
        forced["selection_mode"] = args.include_selection_mode
        rows.append(forced)
        seen_keys.add(key)
    rows.sort(key=lambda item: (item.get("part_name"), float(item.get("start") or 0.0), float(item.get("end") or 0.0)))
    output_payload = {
        **payload,
        "version": f"{payload.get('version')}-filtered-subset-v1",
        "source_json": str(args.input_json),
        "flat_candidates": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, rows)
    print(f"kept={len(rows)} -> {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()
