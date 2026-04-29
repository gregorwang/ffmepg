from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v14_shorttrim120")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v15_coarseaccept")
QUEUE_ORDER = [
    "first_pass_match_fix",
    "remaining_match_fix",
    "unmatched_rich",
    "unmatched_rest",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Close remaining Phase C match-fix queues with coarse speed-first keep decisions."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> None:
    args = parse_args()
    source_manifest = load_json(args.input_dir / "manifest.json")
    auto_rows: list[dict[str, Any]] = []
    queue_summaries: list[dict[str, Any]] = []

    for queue_name in QUEUE_ORDER:
        rows = load_jsonl(args.input_dir / f"{queue_name}_rows.jsonl")
        kept_rows: list[dict[str, Any]] = []
        coarse_keep_count = 0

        for row in rows:
            if queue_name in {"first_pass_match_fix", "remaining_match_fix"}:
                auto_rows.append(
                    {
                        "queue_name": queue_name,
                        "focus_rank": row.get("focus_rank"),
                        "part_name": row.get("part_name"),
                        "clip_name": row.get("clip_name"),
                        "english_cue_id": row.get("english_cue_id"),
                        "status": row.get("status"),
                        "match_origin": row.get("match_origin"),
                        "source_clip_mismatch": row.get("source_clip_mismatch"),
                        "english_text": row.get("english_text"),
                        "current_chinese_text": row.get("current_chinese_text"),
                        "auto_decision": "keep_current_match",
                        "auto_reason": "coarse-speed-accept-residual-matchfix",
                    }
                )
                coarse_keep_count += 1
            else:
                kept_rows.append(row)

        write_jsonl(args.output_dir / f"{queue_name}_rows.jsonl", kept_rows)
        write_tsv(
            args.output_dir / f"{queue_name}_rows.tsv",
            kept_rows,
            list(kept_rows[0].keys()) if kept_rows else list(rows[0].keys()) if rows else [],
        )
        queue_summaries.append(
            {
                "queue_name": queue_name,
                "source_row_count": len(rows),
                "kept_row_count": len(kept_rows),
                "trimmed_row_count": len(rows) - len(kept_rows),
                "coarse_keep_count": coarse_keep_count,
            }
        )

    total_source = sum(int(item["source_row_count"]) for item in queue_summaries)
    total_kept = sum(int(item["kept_row_count"]) for item in queue_summaries)
    total_trimmed = total_source - total_kept
    manifest = {
        "source_input_dir": str(args.input_dir),
        "source_review_row_count": total_source,
        "trimmed_review_row_count": total_trimmed,
        "kept_review_row_count": total_kept,
        "coarse_keep_count": len(auto_rows),
        "queue_summaries": queue_summaries,
    }
    write_json(args.output_dir / "manifest.json", manifest)
    write_tsv(
        args.output_dir / "queue_summary.tsv",
        queue_summaries,
        [
            "queue_name",
            "source_row_count",
            "kept_row_count",
            "trimmed_row_count",
            "coarse_keep_count",
        ],
    )
    write_tsv(
        args.output_dir / "auto_decisions.tsv",
        auto_rows,
        [
            "queue_name",
            "focus_rank",
            "part_name",
            "clip_name",
            "english_cue_id",
            "status",
            "match_origin",
            "source_clip_mismatch",
            "english_text",
            "current_chinese_text",
            "auto_decision",
            "auto_reason",
        ],
    )
    write_jsonl(args.output_dir / "auto_decisions.jsonl", auto_rows)
    print(f"wrote coarse-accept refined screening pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
