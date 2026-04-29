from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from phase_b_sequence_align import prepare_english_text


DEFAULT_INPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v1")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v2")
_UI_ONLY_RE = re.compile(r"^[A-Z0-9 '&:,.!?/-]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refine the Phase C LLM screening pack into a smaller model-facing queue.")
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


def low_value_reason(row: dict[str, Any]) -> str | None:
    english_text = str(row.get("english_text") or "").strip()
    semantic = prepare_english_text(english_text)
    review_bucket = str(row.get("review_bucket") or "")
    current_chinese = str(row.get("current_chinese_text") or "").strip()
    preview = str(row.get("estimated_chinese_preview") or "").strip()
    word_count = len([token for token in english_text.replace("\n", " ").split(" ") if token])

    if review_bucket != "needs-review-unmatched":
        return None
    if not semantic:
        return "empty-english-semantic"
    if _UI_ONLY_RE.fullmatch(english_text) and word_count <= 8:
        return "ui-only"
    if word_count <= 3 and not current_chinese and not preview:
        return "too-short-no-preview"
    return None


def model_bucket(row: dict[str, Any]) -> str:
    review_bucket = str(row.get("review_bucket") or "")
    if review_bucket == "needs-review-low":
        return "model-review-low-match"
    if review_bucket == "needs-review-medium":
        return "model-review-medium-match"
    if review_bucket == "needs-review-auto-high":
        return "model-review-auto-high"
    return "model-review-unmatched"


def model_priority(row: dict[str, Any]) -> int:
    bucket = model_bucket(row)
    return {
        "model-review-low-match": 0,
        "model-review-medium-match": 1,
        "model-review-auto-high": 2,
        "model-review-unmatched": 3,
    }[bucket]


def prompt_template() -> str:
    return """你会收到 Phase C 的精炼筛查 JSON 行。

你的任务是只做快速判别，不要长篇解释。

输出 JSON：
{
  "review_rank": 123,
  "decision": "keep_current_match | reject_current_match | suggest_new_match | no_match | unsure",
  "confidence": 0.0,
  "suggested_chinese_text": "",
  "reason": ""
}

规则：
- `model-review-low-match` 与 `model-review-medium-match`：先判当前中文是否应保留。
- `model-review-auto-high`：默认保守，只有明显错配才拒绝。
- `model-review-unmatched`：优先基于 `estimated_chinese_preview`、前后锚点和英文上下文，给出中文建议；没有把握就 `no_match`。
- 不要编造新剧情，不要输出额外字段。
"""


def main() -> None:
    args = parse_args()
    input_manifest = load_json(args.input_dir / "manifest.json")
    review_rows = load_jsonl(args.input_dir / "review_rows.jsonl")

    screen_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    skip_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()

    for row in review_rows:
        reason = low_value_reason(row)
        if reason:
            skipped = dict(row)
            skipped["skip_reason"] = reason
            skipped_rows.append(skipped)
            skip_counts[reason] += 1
            continue

        item = dict(row)
        item["model_bucket"] = model_bucket(item)
        item["model_priority"] = model_priority(item)
        bucket_counts[str(item["model_bucket"])] += 1
        screen_rows.append(item)

    screen_rows.sort(
        key=lambda item: (
            int(item["model_priority"]),
            item["part_name"],
            item["clip_name"],
            int(item["english_local_index"]),
        )
    )
    for screen_rank, row in enumerate(screen_rows, start=1):
        row["screen_rank"] = screen_rank

    batch_rows: list[dict[str, Any]] = []
    for batch_start in range(0, len(screen_rows), max(args.batch_size, 1)):
        chunk = screen_rows[batch_start : batch_start + args.batch_size]
        batch_no = (batch_start // max(args.batch_size, 1)) + 1
        path = args.output_dir / "batches" / f"screen_batch_{batch_no:03d}.jsonl"
        write_jsonl(path, chunk)
        batch_rows.append(
            {
                "batch_no": batch_no,
                "row_count": len(chunk),
                "from_screen_rank": chunk[0]["screen_rank"],
                "to_screen_rank": chunk[-1]["screen_rank"],
                "path": str(path),
            }
        )

    fields = [
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
    skipped_fields = ["skip_reason"] + [field for field in fields if field != "screen_rank" and field != "model_priority" and field != "model_bucket"]

    manifest = {
        "source_input_dir": str(args.input_dir),
        "source_total_rows": int(input_manifest.get("total_rows") or 0),
        "source_review_rows": int(input_manifest.get("review_rows") or 0),
        "screen_rows": len(screen_rows),
        "skipped_rows": len(skipped_rows),
        "skip_counts": dict(sorted(skip_counts.items())),
        "model_bucket_counts": dict(sorted(bucket_counts.items())),
        "batch_size": args.batch_size,
        "batch_count": len(batch_rows),
        "batches": batch_rows,
    }

    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "prompt_template.json", {"prompt_markdown": prompt_template()})
    (args.output_dir / "screening_prompt.md").write_text(prompt_template(), encoding="utf-8")
    write_tsv(args.output_dir / "screen_rows.tsv", screen_rows, fields)
    write_jsonl(args.output_dir / "screen_rows.jsonl", screen_rows)
    write_tsv(args.output_dir / "skipped_rows.tsv", skipped_rows, skipped_fields)
    write_jsonl(args.output_dir / "skipped_rows.jsonl", skipped_rows)
    print(f"wrote refined llm screening pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
