from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_phase_b_cue_local_align import write_tsv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply deterministic row overrides to a Phase B flat-candidate JSON."
    )
    parser.add_argument("--input-json", type=Path, required=True)
    parser.add_argument("--overrides-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-tsv", type=Path, required=True)
    return parser.parse_args()


def _key_for_row(row: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    return (
        str(row.get("part_name") or ""),
        tuple(str(item) for item in (row.get("english_cue_ids") or [])),
    )


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    overrides_payload = json.loads(args.overrides_json.read_text(encoding="utf-8"))

    override_map: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for item in overrides_payload.get("overrides") or []:
        key = (
            str(item["part_name"]),
            tuple(str(cue_id) for cue_id in item["english_cue_ids"]),
        )
        override_map[key] = dict(item.get("fields") or {})

    rows: list[dict[str, Any]] = []
    applied = 0
    for row in payload.get("flat_candidates") or []:
        updated = dict(row)
        fields = override_map.get(_key_for_row(row))
        if fields:
            updated.update(fields)
            applied += 1
        rows.append(updated)

    output_payload = {
        **payload,
        "version": f"{payload.get('version')}-row-overrides-v1",
        "source_json": str(args.input_json),
        "overrides_json": str(args.overrides_json),
        "flat_candidates": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, rows)
    print(f"applied={applied} -> {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()

