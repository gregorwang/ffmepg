from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v2")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v3")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split the refined Phase C LLM screening pack into model-facing subqueues.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--match-fix-batch-size", type=int, default=200)
    parser.add_argument("--unmatched-batch-size", type=int, default=200)
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


def write_batches(base_dir: Path, rows: list[dict[str, Any]], batch_size: int, prefix: str) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    if not rows:
        return manifests
    for offset in range(0, len(rows), max(batch_size, 1)):
        chunk = rows[offset : offset + batch_size]
        batch_no = (offset // max(batch_size, 1)) + 1
        path = base_dir / f"{prefix}_{batch_no:03d}.jsonl"
        write_jsonl(path, chunk)
        manifests.append(
            {
                "batch_no": batch_no,
                "row_count": len(chunk),
                "from_rank": offset + 1,
                "to_rank": offset + len(chunk),
                "path": str(path),
            }
        )
    return manifests


def run_order_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Phase C Model Run Order",
        "",
        "1. Run `match_fix` first. This queue is smaller and has the highest immediate payoff because it checks existing auto matches.",
        "2. Run `unmatched` second. This queue is much larger and is for discovery rather than correction.",
        "",
        "## Counts",
        "",
        f"- `match_fix_rows`: {manifest['match_fix_rows']}",
        f"- `unmatched_rows`: {manifest['unmatched_rows']}",
        f"- `match_fix_batches`: {manifest['match_fix_batch_count']}",
        f"- `unmatched_batches`: {manifest['unmatched_batch_count']}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    input_manifest = load_json(args.input_dir / "manifest.json")
    rows = load_jsonl(args.input_dir / "screen_rows.jsonl")

    match_fix_rows = [row for row in rows if str(row.get("model_bucket") or "") != "model-review-unmatched"]
    unmatched_rows = [row for row in rows if str(row.get("model_bucket") or "") == "model-review-unmatched"]

    match_fix_rows.sort(key=lambda row: (int(row["model_priority"]), row["part_name"], row["clip_name"], int(row["english_local_index"])))
    unmatched_rows.sort(key=lambda row: (row["part_name"], row["clip_name"], int(row["english_local_index"])))

    for index, row in enumerate(match_fix_rows, start=1):
        row["subqueue_rank"] = index
    for index, row in enumerate(unmatched_rows, start=1):
        row["subqueue_rank"] = index

    fields = [
        "subqueue_rank",
        "screen_rank",
        "review_rank",
        "queue_rank",
        "model_priority",
        "model_bucket",
        "review_bucket",
        "part_name",
        "clip_name",
        "clip_english_count",
        "clip_chinese_count",
        "english_local_index",
        "english_cue_id",
        "start",
        "end",
        "duration",
        "english_text",
        "english_context_text",
        "status",
        "match_origin",
        "match_score",
        "source_clip",
        "source_clip_mismatch",
        "current_chinese_cue_ids",
        "current_chinese_text",
        "estimated_chinese_center_pos",
        "estimated_chinese_preview_indices",
        "estimated_chinese_preview",
        "nearest_prev_matched_ids",
        "nearest_prev_matched_text",
        "nearest_next_matched_ids",
        "nearest_next_matched_text",
        "notes",
    ]

    match_fix_batches = write_batches(args.output_dir / "match_fix_batches", match_fix_rows, args.match_fix_batch_size, "match_fix_batch")
    unmatched_batches = write_batches(args.output_dir / "unmatched_batches", unmatched_rows, args.unmatched_batch_size, "unmatched_batch")

    manifest = {
        "source_input_dir": str(args.input_dir),
        "source_screen_rows": int(input_manifest.get("screen_rows") or 0),
        "match_fix_rows": len(match_fix_rows),
        "unmatched_rows": len(unmatched_rows),
        "match_fix_batch_size": args.match_fix_batch_size,
        "unmatched_batch_size": args.unmatched_batch_size,
        "match_fix_batch_count": len(match_fix_batches),
        "unmatched_batch_count": len(unmatched_batches),
        "match_fix_batches": match_fix_batches,
        "unmatched_batches": unmatched_batches,
    }

    write_json(args.output_dir / "manifest.json", manifest)
    (args.output_dir / "RUN_ORDER.md").write_text(run_order_markdown(manifest), encoding="utf-8")
    write_tsv(args.output_dir / "match_fix_rows.tsv", match_fix_rows, fields)
    write_jsonl(args.output_dir / "match_fix_rows.jsonl", match_fix_rows)
    write_tsv(args.output_dir / "unmatched_rows.tsv", unmatched_rows, fields)
    write_jsonl(args.output_dir / "unmatched_rows.jsonl", unmatched_rows)
    print(f"wrote specialized llm screening pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
