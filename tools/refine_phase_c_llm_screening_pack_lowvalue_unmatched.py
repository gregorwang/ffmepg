from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v6_speakertrim")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v7_shorttrim")
JUNK_PATTERNS = {
    "w (full)",
    "metsubushi (full)",
    "aeloval men",
    "lat ath mon",
    "(((e)) ((e))",
}
JUNK_SUBSTRINGS = [
    "irit meter",
    "iwant",
    "gotit",
    "perfert",
    "engo:atsu.:",
]
QUEUE_ORDER = [
    "first_pass_match_fix",
    "remaining_match_fix",
    "unmatched_rich",
    "unmatched_rest",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drop low-value unmatched rows from the Phase C screening pack.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--short-len-threshold", type=int, default=24)
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


def is_low_value_unmatched(row: dict[str, Any], short_len_threshold: int) -> tuple[bool, str]:
    if str(row.get("status") or "") != "unmatched":
        return False, ""
    text = str(row.get("english_text") or "").strip()
    lowered = text.lower()
    if lowered in JUNK_PATTERNS:
        return True, "junk-pattern"
    if any(pattern in lowered for pattern in JUNK_SUBSTRINGS):
        return True, "junk-substring"
    if len(text) <= short_len_threshold:
        return True, f"short-unmatched<={short_len_threshold}"
    return False, ""


def main() -> None:
    args = parse_args()
    source_manifest = load_json(args.input_dir / "manifest.json")
    dropped_rows: list[dict[str, Any]] = []
    queue_summaries: list[dict[str, Any]] = []

    for queue_name in QUEUE_ORDER:
        jsonl_rows_path = args.input_dir / f"{queue_name}_rows.jsonl"
        rows = load_jsonl(jsonl_rows_path)
        kept_rows: list[dict[str, Any]] = []
        dropped_count = 0
        for row in rows:
            should_drop, reason = is_low_value_unmatched(row, args.short_len_threshold)
            if should_drop:
                dropped_rows.append(
                    {
                        "queue_name": queue_name,
                        "focus_rank": row.get("focus_rank"),
                        "part_name": row.get("part_name"),
                        "clip_name": row.get("clip_name"),
                        "english_cue_id": row.get("english_cue_id"),
                        "english_text": row.get("english_text"),
                        "drop_reason": reason,
                    }
                )
                dropped_count += 1
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
                "dropped_row_count": dropped_count,
            }
        )

    manifest = {
        "source_input_dir": str(args.input_dir),
        "source_review_row_count": sum(int(item["source_row_count"]) for item in queue_summaries),
        "kept_review_row_count": sum(int(item["kept_row_count"]) for item in queue_summaries),
        "dropped_review_row_count": sum(int(item["dropped_row_count"]) for item in queue_summaries),
        "short_len_threshold": int(args.short_len_threshold),
        "queue_summaries": queue_summaries,
    }
    write_json(args.output_dir / "manifest.json", manifest)
    write_tsv(
        args.output_dir / "queue_summary.tsv",
        queue_summaries,
        ["queue_name", "source_row_count", "kept_row_count", "dropped_row_count"],
    )
    write_tsv(
        args.output_dir / "dropped_rows.tsv",
        dropped_rows,
        ["queue_name", "focus_rank", "part_name", "clip_name", "english_cue_id", "english_text", "drop_reason"],
    )
    write_jsonl(args.output_dir / "dropped_rows.jsonl", dropped_rows)
    print(f"wrote low-value-unmatched refined screening pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
