from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_phase_b_cue_local_align import write_tsv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge multiple Phase B flat-candidate JSON subsets into one deduplicated subset."
    )
    parser.add_argument("--input-json", action="append", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-tsv", type=Path, required=True)
    return parser.parse_args()


def row_key(row: dict[str, Any]) -> tuple[str, tuple[str, ...], tuple[str, ...], float, float]:
    return (
        str(row.get("part_name") or ""),
        tuple(str(item) for item in (row.get("english_cue_ids") or [])),
        tuple(str(item) for item in (row.get("chinese_cue_ids") or [])),
        float(row.get("start") or 0.0),
        float(row.get("end") or 0.0),
    )


def main() -> None:
    args = parse_args()
    merged_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], tuple[str, ...], float, float]] = set()
    source_jsons: list[str] = []

    for raw_path in args.input_json:
        path = Path(raw_path)
        source_jsons.append(str(path))
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("flat_candidates") or []:
            key = row_key(row)
            if key in seen:
                continue
            seen.add(key)
            merged_rows.append(dict(row))

    merged_rows.sort(key=lambda item: (item.get("part_name"), float(item.get("start") or 0.0), float(item.get("end") or 0.0)))
    output_payload = {
        "version": "phase-b-merged-subset-v1",
        "source_jsons": source_jsons,
        "flat_candidates": merged_rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, merged_rows)
    print(f"merged={len(merged_rows)} -> {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()

