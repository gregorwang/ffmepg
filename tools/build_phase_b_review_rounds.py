from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROUND_MAP = {
    "check_compression_or_omission": "round_a_compression",
    "check_wording_and_merge": "round_b_wording",
    "confirm_anchor_alignment": "round_c_anchor",
    "confirm_partial_alignment": "round_d_partial",
    "spot_check_low_score": "round_e_low_score",
    "general_review": "round_z_misc",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split a curation context pack into review rounds by action type."
    )
    parser.add_argument("--context-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "curation_id",
        "priority",
        "review_action",
        "part_name",
        "source_clip",
        "start",
        "end",
        "match_score",
        "selection_mode",
        "reason_tags",
        "english_text",
        "chinese_text",
        "prev_context",
        "next_context",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "curation_id": row["curation_id"],
                    "priority": row["priority"],
                    "review_action": row["review_action"],
                    "part_name": row["part_name"],
                    "source_clip": row["source_clip"],
                    "start": row["start"],
                    "end": row["end"],
                    "match_score": row["match_score"],
                    "selection_mode": row["selection_mode"],
                    "reason_tags": ",".join(row["reason_tags"]),
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                    "prev_context": " || ".join(row["prev_context"]),
                    "next_context": " || ".join(row["next_context"]),
                }
            )


def main() -> None:
    args = parse_args()
    context_payload = json.loads((args.context_dir / "context_items.json").read_text(encoding="utf-8"))
    items = list(context_payload["items"])

    rounds: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        round_name = ROUND_MAP.get(item["review_action"], "round_z_misc")
        rounds[round_name].append(item)

    manifest = {
        "version": "phase-b-review-rounds-v1",
        "source_context_dir": str(args.context_dir),
        "source_item_count": len(items),
        "rounds": [],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for round_name, rows in sorted(rounds.items()):
        rows.sort(key=lambda row: (row["part_name"], row["start"], row["curation_id"]))
        write_json(args.output_dir / f"{round_name}.json", {"items": rows})
        write_tsv(args.output_dir / f"{round_name}.tsv", rows)
        manifest["rounds"].append(
            {
                "name": round_name,
                "item_count": len(rows),
                "parts": sorted({row["part_name"].replace("ghost-yotei-", "") for row in rows}),
            }
        )

    write_json(args.output_dir / "manifest.json", manifest)
    print(f"wrote review rounds -> {args.output_dir}")


if __name__ == "__main__":
    main()

