from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v3")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v4")
_ZH_FRAGMENT_RE = re.compile(r"^[：:·.。，“”‘’、；;？！!?（）()]{0,2}[\u4e00-\u9fff]{0,4}[：:·.。，“”‘’、；;？！!?（）()]{0,2}$")
_OCR_NOISE_RE = re.compile(r"[A-Za-z]{2,}|[·]{1,}|[^\w\s\u4e00-\u9fff：:，。！？、（）()“”‘’-]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tier the Phase C LLM screening pack into higher-value model queues.")
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


def short_chinese_fragment(text: str) -> bool:
    compact = (text or "").strip()
    if not compact:
        return False
    if len(compact) <= 5:
        return True
    return bool(_ZH_FRAGMENT_RE.fullmatch(compact))


def ocr_noise_ratio(text: str) -> float:
    compact = (text or "").strip()
    if not compact:
        return 0.0
    noise_hits = len(_OCR_NOISE_RE.findall(compact))
    return noise_hits / max(len(compact), 1)


def match_fix_risk_score(row: dict[str, Any]) -> float:
    score = 0.0
    origin = str(row.get("match_origin") or "")
    review_bucket = str(row.get("review_bucket") or "")
    current_text = str(row.get("current_chinese_text") or "")
    match_score = float(row.get("match_score") or 0.0)

    if bool(row.get("source_clip_mismatch")):
        score += 6.0
    if review_bucket == "needs-review-low":
        score += 4.0
    elif review_bucket == "needs-review-medium":
        score += 2.0
    elif review_bucket == "needs-review-auto-high":
        score += 1.0

    score += max(0.0, 0.8 - match_score) * 10.0

    if origin == "group-clip-local-v1":
        score += 3.0
    elif origin == "group-anchor-window-v1":
        score += 2.5
    elif origin == "auto-anchor-window-v1":
        score += 1.5
    elif origin == "auto-clip-local-v1":
        score += 1.0

    if short_chinese_fragment(current_text):
        score += 2.5
    if ocr_noise_ratio(current_text) >= 0.08:
        score += 2.0
    if len(current_text.strip()) <= 1:
        score += 2.0
    return round(score, 4)


def unmatched_value_score(row: dict[str, Any]) -> float:
    score = 0.0
    preview = str(row.get("estimated_chinese_preview") or "")
    prev_text = str(row.get("nearest_prev_matched_text") or "")
    next_text = str(row.get("nearest_next_matched_text") or "")
    english_text = str(row.get("english_text") or "")
    duration = float(row.get("duration") or 0.0)

    if preview:
        score += min(len(preview), 80) / 20.0
        if ocr_noise_ratio(preview) < 0.06:
            score += 1.0
    if prev_text:
        score += 0.8
    if next_text:
        score += 0.8
    if len(english_text.split()) >= 4:
        score += 0.6
    if duration >= 2.0:
        score += 0.3
    return round(score, 4)


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
    return "\n".join(
        [
            "# Phase C Tiered Model Run Order",
            "",
            "1. Run `match_fix_hot` first.",
            "2. Run `match_fix_rest` second.",
            "3. Run `unmatched_rich` third.",
            "4. Run `unmatched_rest` last.",
            "",
            "## Counts",
            "",
            f"- `match_fix_hot_rows`: {manifest['match_fix_hot_rows']}",
            f"- `match_fix_rest_rows`: {manifest['match_fix_rest_rows']}",
            f"- `unmatched_rich_rows`: {manifest['unmatched_rich_rows']}",
            f"- `unmatched_rest_rows`: {manifest['unmatched_rest_rows']}",
        ]
    )


def main() -> None:
    args = parse_args()
    manifest_in = load_json(args.input_dir / "manifest.json")
    match_fix_rows = load_jsonl(args.input_dir / "match_fix_rows.jsonl")
    unmatched_rows = load_jsonl(args.input_dir / "unmatched_rows.jsonl")

    for row in match_fix_rows:
        row["risk_score"] = match_fix_risk_score(row)
    for row in unmatched_rows:
        row["value_score"] = unmatched_value_score(row)

    match_fix_rows.sort(
        key=lambda row: (
            -float(row["risk_score"]),
            float(row.get("match_score") or 0.0),
            row["part_name"],
            row["clip_name"],
            int(row["english_local_index"]),
        )
    )
    unmatched_rows.sort(
        key=lambda row: (
            -float(row["value_score"]),
            row["part_name"],
            row["clip_name"],
            int(row["english_local_index"]),
        )
    )

    match_fix_hot = [row for row in match_fix_rows if float(row["risk_score"]) >= 4.0]
    match_fix_rest = [row for row in match_fix_rows if float(row["risk_score"]) < 4.0]
    unmatched_rich = [row for row in unmatched_rows if float(row["value_score"]) >= 4.0]
    unmatched_rest = [row for row in unmatched_rows if float(row["value_score"]) < 4.0]

    for idx, row in enumerate(match_fix_hot, start=1):
        row["tier_rank"] = idx
    for idx, row in enumerate(match_fix_rest, start=1):
        row["tier_rank"] = idx
    for idx, row in enumerate(unmatched_rich, start=1):
        row["tier_rank"] = idx
    for idx, row in enumerate(unmatched_rest, start=1):
        row["tier_rank"] = idx

    match_fix_hot_batches = write_batches(args.output_dir / "match_fix_hot_batches", match_fix_hot, args.batch_size, "match_fix_hot")
    match_fix_rest_batches = write_batches(args.output_dir / "match_fix_rest_batches", match_fix_rest, args.batch_size, "match_fix_rest")
    unmatched_rich_batches = write_batches(args.output_dir / "unmatched_rich_batches", unmatched_rich, args.batch_size, "unmatched_rich")
    unmatched_rest_batches = write_batches(args.output_dir / "unmatched_rest_batches", unmatched_rest, args.batch_size, "unmatched_rest")

    fields = [
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
        "source_match_fix_rows": len(match_fix_rows),
        "source_unmatched_rows": len(unmatched_rows),
        "match_fix_hot_rows": len(match_fix_hot),
        "match_fix_rest_rows": len(match_fix_rest),
        "unmatched_rich_rows": len(unmatched_rich),
        "unmatched_rest_rows": len(unmatched_rest),
        "batch_size": args.batch_size,
        "match_fix_hot_batch_count": len(match_fix_hot_batches),
        "match_fix_rest_batch_count": len(match_fix_rest_batches),
        "unmatched_rich_batch_count": len(unmatched_rich_batches),
        "unmatched_rest_batch_count": len(unmatched_rest_batches),
        "match_fix_hot_batches": match_fix_hot_batches,
        "match_fix_rest_batches": match_fix_rest_batches,
        "unmatched_rich_batches": unmatched_rich_batches,
        "unmatched_rest_batches": unmatched_rest_batches,
    }

    write_json(args.output_dir / "manifest.json", manifest)
    (args.output_dir / "RUN_ORDER.md").write_text(run_order_markdown(manifest), encoding="utf-8")
    write_tsv(args.output_dir / "match_fix_hot_rows.tsv", match_fix_hot, fields)
    write_jsonl(args.output_dir / "match_fix_hot_rows.jsonl", match_fix_hot)
    write_tsv(args.output_dir / "match_fix_rest_rows.tsv", match_fix_rest, fields)
    write_jsonl(args.output_dir / "match_fix_rest_rows.jsonl", match_fix_rest)
    write_tsv(args.output_dir / "unmatched_rich_rows.tsv", unmatched_rich, fields)
    write_jsonl(args.output_dir / "unmatched_rich_rows.jsonl", unmatched_rich)
    write_tsv(args.output_dir / "unmatched_rest_rows.tsv", unmatched_rest, fields)
    write_jsonl(args.output_dir / "unmatched_rest_rows.jsonl", unmatched_rest)
    print(f"wrote tiered llm screening pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
