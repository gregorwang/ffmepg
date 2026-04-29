from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v4")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v5")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Focus the Phase C tiered screening pack into a first-pass model queue.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=150)
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


def is_first_pass_match_fix(row: dict[str, Any]) -> bool:
    if str(row.get("source_clip_mismatch")) != "True":
        return False
    return str(row.get("match_origin") or "") in {"auto-anchor-window-v1", "group-anchor-window-v1"}


def run_order_markdown(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase C Focused Model Run Order",
            "",
            "1. Run `first_pass_match_fix` first. This is the most concentrated queue of high-risk cross-clip anchor mismatches.",
            "2. Run `remaining_match_fix` second.",
            "3. Run `unmatched_rich` third.",
            "4. Run `unmatched_rest` last.",
            "",
            "## Counts",
            "",
            f"- `first_pass_match_fix_rows`: {manifest['first_pass_match_fix_rows']}",
            f"- `remaining_match_fix_rows`: {manifest['remaining_match_fix_rows']}",
            f"- `unmatched_rich_rows`: {manifest['unmatched_rich_rows']}",
            f"- `unmatched_rest_rows`: {manifest['unmatched_rest_rows']}",
        ]
    )


def main() -> None:
    args = parse_args()
    manifest_in = load_json(args.input_dir / "manifest.json")
    match_fix_hot_rows = load_jsonl(args.input_dir / "match_fix_hot_rows.jsonl")
    match_fix_rest_rows = load_jsonl(args.input_dir / "match_fix_rest_rows.jsonl")
    unmatched_rich_rows = load_jsonl(args.input_dir / "unmatched_rich_rows.jsonl")
    unmatched_rest_rows = load_jsonl(args.input_dir / "unmatched_rest_rows.jsonl")

    first_pass_match_fix = [row for row in match_fix_hot_rows if is_first_pass_match_fix(row)]
    remaining_match_fix = [row for row in match_fix_hot_rows if not is_first_pass_match_fix(row)] + list(match_fix_rest_rows)

    for idx, row in enumerate(first_pass_match_fix, start=1):
        row["focus_rank"] = idx
    for idx, row in enumerate(remaining_match_fix, start=1):
        row["focus_rank"] = idx
    for idx, row in enumerate(unmatched_rich_rows, start=1):
        row["focus_rank"] = idx
    for idx, row in enumerate(unmatched_rest_rows, start=1):
        row["focus_rank"] = idx

    first_pass_batches = write_batches(args.output_dir / "first_pass_match_fix_batches", first_pass_match_fix, args.batch_size, "first_pass_match_fix")
    remaining_match_fix_batches = write_batches(args.output_dir / "remaining_match_fix_batches", remaining_match_fix, args.batch_size, "remaining_match_fix")
    unmatched_rich_batches = write_batches(args.output_dir / "unmatched_rich_batches", unmatched_rich_rows, args.batch_size, "unmatched_rich")
    unmatched_rest_batches = write_batches(args.output_dir / "unmatched_rest_batches", unmatched_rest_rows, args.batch_size, "unmatched_rest")

    fields = [
        "focus_rank",
        "tier_rank",
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
        "risk_score",
        "value_score",
    ]

    manifest = {
        "source_input_dir": str(args.input_dir),
        "source_match_fix_hot_rows": int(manifest_in.get("match_fix_hot_rows") or 0),
        "source_match_fix_rest_rows": int(manifest_in.get("match_fix_rest_rows") or 0),
        "source_unmatched_rich_rows": int(manifest_in.get("unmatched_rich_rows") or 0),
        "source_unmatched_rest_rows": int(manifest_in.get("unmatched_rest_rows") or 0),
        "first_pass_match_fix_rows": len(first_pass_match_fix),
        "remaining_match_fix_rows": len(remaining_match_fix),
        "unmatched_rich_rows": len(unmatched_rich_rows),
        "unmatched_rest_rows": len(unmatched_rest_rows),
        "batch_size": args.batch_size,
        "first_pass_match_fix_batch_count": len(first_pass_batches),
        "remaining_match_fix_batch_count": len(remaining_match_fix_batches),
        "unmatched_rich_batch_count": len(unmatched_rich_batches),
        "unmatched_rest_batch_count": len(unmatched_rest_batches),
        "first_pass_match_fix_batches": first_pass_batches,
        "remaining_match_fix_batches": remaining_match_fix_batches,
        "unmatched_rich_batches": unmatched_rich_batches,
        "unmatched_rest_batches": unmatched_rest_batches,
    }

    write_json(args.output_dir / "manifest.json", manifest)
    (args.output_dir / "RUN_ORDER.md").write_text(run_order_markdown(manifest), encoding="utf-8")
    write_tsv(args.output_dir / "first_pass_match_fix_rows.tsv", first_pass_match_fix, fields)
    write_jsonl(args.output_dir / "first_pass_match_fix_rows.jsonl", first_pass_match_fix)
    write_tsv(args.output_dir / "remaining_match_fix_rows.tsv", remaining_match_fix, fields)
    write_jsonl(args.output_dir / "remaining_match_fix_rows.jsonl", remaining_match_fix)
    write_tsv(args.output_dir / "unmatched_rich_rows.tsv", unmatched_rich_rows, fields)
    write_jsonl(args.output_dir / "unmatched_rich_rows.jsonl", unmatched_rich_rows)
    write_tsv(args.output_dir / "unmatched_rest_rows.tsv", unmatched_rest_rows, fields)
    write_jsonl(args.output_dir / "unmatched_rest_rows.jsonl", unmatched_rest_rows)
    print(f"wrote focused llm screening pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
