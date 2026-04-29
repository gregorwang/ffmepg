from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from build_phase_c_fulltrack_rebuild import (
    DEFAULT_CHINESE_OCR_ROOT,
    DEFAULT_ENGLISH_OCR_ROOT,
    DEFAULT_MAPPING_JSON,
    FullChineseCue,
    FullEnglishCue,
    assign_clip_english_cues,
    load_full_chinese_cues,
    load_full_english_cues,
)


DEFAULT_PHASE_C_JSON = Path("scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2/all_segments.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a full Phase C screening pack for batch LLM review.")
    parser.add_argument("--mapping-json", type=Path, default=DEFAULT_MAPPING_JSON)
    parser.add_argument("--phase-c-json", type=Path, default=DEFAULT_PHASE_C_JSON)
    parser.add_argument("--english-ocr-root", type=Path, default=DEFAULT_ENGLISH_OCR_ROOT)
    parser.add_argument("--chinese-ocr-root", type=Path, default=DEFAULT_CHINESE_OCR_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--english-context", type=int, default=2)
    parser.add_argument("--chinese-window-radius", type=int, default=3)
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def cue_text_window(cues: list[FullEnglishCue], center: int, radius: int) -> str:
    start = max(0, center - radius)
    end = min(len(cues), center + radius + 1)
    return " ".join(cue.text.strip() for cue in cues[start:end] if cue.text.strip()).strip()


def chinese_preview(chinese_cues: list[FullChineseCue], position: int, radius: int) -> tuple[str, str]:
    if not chinese_cues:
        return "", ""
    start = max(0, position - radius)
    end = min(len(chinese_cues), position + radius + 1)
    preview = " ".join(cue.text.strip() for cue in chinese_cues[start:end] if cue.text.strip()).strip()
    indices = ",".join(str(cue.cue_index) for cue in chinese_cues[start:end])
    return indices, preview


def review_bucket(row: dict[str, Any]) -> str:
    origin = str(row.get("match_origin") or "")
    status = str(row.get("status") or "unmatched")
    if origin == "reviewed-master":
        return "locked-anchor"
    if status == "unmatched":
        return "needs-review-unmatched"
    if status == "matched-low":
        return "needs-review-low"
    if status in {"matched-medium", "merged-1n", "merged-n1"}:
        return "needs-review-medium"
    return "needs-review-auto-high"


def queue_priority(bucket: str) -> int:
    return {
        "needs-review-unmatched": 0,
        "needs-review-low": 1,
        "needs-review-medium": 2,
        "needs-review-auto-high": 3,
        "locked-anchor": 9,
    }.get(bucket, 9)


def nearest_matched_context(
    clip_rows: list[dict[str, Any]],
    center: int,
) -> tuple[str, str, str, str]:
    prev_text = ""
    prev_ids = ""
    next_text = ""
    next_ids = ""

    for idx in range(center - 1, -1, -1):
        row = clip_rows[idx]
        if str(row.get("status") or "") != "unmatched" and str(row.get("chinese_text") or "").strip():
            prev_text = str(row.get("chinese_text") or "")
            prev_ids = ",".join(str(item) for item in (row.get("chinese_cue_ids") or []))
            break

    for idx in range(center + 1, len(clip_rows)):
        row = clip_rows[idx]
        if str(row.get("status") or "") != "unmatched" and str(row.get("chinese_text") or "").strip():
            next_text = str(row.get("chinese_text") or "")
            next_ids = ",".join(str(item) for item in (row.get("chinese_cue_ids") or []))
            break

    return prev_ids, prev_text, next_ids, next_text


def prompt_template() -> str:
    return """你会收到一行一条的 Phase C 双语筛查 JSON。

目标：
1. 判断当前 `current_chinese_text` 是否可保留。
2. 如果当前为空或明显不对，只能基于该行自带的上下文与 `estimated_chinese_preview` 提出更合理的中文候选。
3. 不要编造剧情外信息；优先使用已给出的中文窗口文本片段。

建议输出 JSON：
{
  "queue_rank": 123,
  "decision": "keep_current_match | replace_match | no_match | unsure",
  "confidence": 0.0,
  "suggested_chinese_text": "",
  "reason": ""
}

判定要点：
- `locked-anchor` 通常可直接跳过或标记 `keep_current_match`
- `needs-review-unmatched` 优先看 `estimated_chinese_preview`
- `needs-review-low` / `needs-review-medium` 先检查当前匹配和英文语义、说话人、前后文是否一致
- 如果中文只是残 OCR 片段、标签碎片、或明显跨句错配，优先 `no_match` 或 `replace_match`
"""


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    phase_payload = json.loads(args.phase_c_json.read_text(encoding="utf-8"))
    phase_rows = list(phase_payload["segments"])

    part_rows: dict[str, list[dict[str, Any]]] = {}
    for row in phase_rows:
        part_rows.setdefault(str(row["part_name"]), []).append(row)

    output_rows: list[dict[str, Any]] = []
    batch_rows: list[dict[str, Any]] = []
    batch_manifests: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for part_info in mapping.get("parts") or []:
        part_name = str(part_info["part_name"])
        english_cues = load_full_english_cues(args.english_ocr_root, part_name)
        clip_assignments = sorted(
            [item for item in mapping.get("clips") or [] if str(item.get("assigned_part") or "") == part_name],
            key=lambda item: int(item.get("clip_order_in_part") or 0),
        )
        english_by_clip = assign_clip_english_cues(english_cues, clip_assignments)
        row_map = {str(row["segment_id"]): row for row in part_rows.get(part_name, [])}

        for clip in clip_assignments:
            clip_name = str(clip["clip_name"])
            clip_english = english_by_clip.get(clip_name, [])
            clip_chinese = load_full_chinese_cues(args.chinese_ocr_root, clip_name)
            clip_rows: list[dict[str, Any]] = []

            for local_index, cue in enumerate(clip_english, start=1):
                row = dict(row_map.get(cue.cue_id) or {})
                row.setdefault("status", "unmatched")
                row.setdefault("match_origin", "none")
                row.setdefault("match_score", None)
                row.setdefault("source_clip", None)
                row.setdefault("chinese_text", "")
                row.setdefault("chinese_cue_ids", [])
                row.setdefault("notes", "")

                bucket = review_bucket(row)
                status = str(row["status"])
                status_counts[status] += 1
                bucket_counts[bucket] += 1

                ratio = 0.0 if len(clip_english) <= 1 else (local_index - 1) / (len(clip_english) - 1)
                estimated_pos = 0 if not clip_chinese else min(len(clip_chinese) - 1, int(round(ratio * (len(clip_chinese) - 1))))
                preview_indices, preview_text = chinese_preview(clip_chinese, estimated_pos, args.chinese_window_radius)
                prev_ids, prev_text, next_ids, next_text = nearest_matched_context(clip_rows, len(clip_rows))

                item = {
                    "queue_rank": 0,
                    "queue_priority": queue_priority(bucket),
                    "review_bucket": bucket,
                    "part_name": part_name,
                    "clip_name": clip_name,
                    "clip_english_count": len(clip_english),
                    "clip_chinese_count": len(clip_chinese),
                    "english_local_index": local_index,
                    "english_cue_id": cue.cue_id,
                    "start": cue.start,
                    "end": cue.end,
                    "duration": round(cue.end - cue.start, 3),
                    "english_text": cue.text,
                    "english_context_text": cue_text_window(clip_english, local_index - 1, args.english_context),
                    "status": status,
                    "match_origin": str(row["match_origin"]),
                    "match_score": row["match_score"],
                    "source_clip": row["source_clip"],
                    "source_clip_mismatch": bool(row.get("source_clip")) and str(row.get("source_clip")) != clip_name,
                    "current_chinese_cue_ids": ",".join(str(item) for item in (row.get("chinese_cue_ids") or [])),
                    "current_chinese_text": str(row.get("chinese_text") or ""),
                    "notes": str(row.get("notes") or ""),
                    "estimated_chinese_center_pos": estimated_pos,
                    "estimated_chinese_preview_indices": preview_indices,
                    "estimated_chinese_preview": preview_text,
                    "nearest_prev_matched_ids": prev_ids,
                    "nearest_prev_matched_text": prev_text,
                    "nearest_next_matched_ids": next_ids,
                    "nearest_next_matched_text": next_text,
                }
                clip_rows.append(item)
                output_rows.append(item)

    output_rows.sort(
        key=lambda item: (
            int(item["queue_priority"]),
            item["part_name"],
            item["clip_name"],
            int(item["english_local_index"]),
        )
    )
    for queue_rank, row in enumerate(output_rows, start=1):
        row["queue_rank"] = queue_rank

    review_rows = [row for row in output_rows if row["review_bucket"] != "locked-anchor"]
    for review_rank, row in enumerate(review_rows, start=1):
        row["review_rank"] = review_rank

    for batch_index in range(0, len(review_rows), max(args.batch_size, 1)):
        chunk = review_rows[batch_index : batch_index + args.batch_size]
        batch_no = (batch_index // max(args.batch_size, 1)) + 1
        batch_path = args.output_dir / "batches" / f"review_batch_{batch_no:03d}.jsonl"
        write_jsonl(batch_path, chunk)
        batch_manifests.append(
            {
                "batch_no": batch_no,
                "row_count": len(chunk),
                "from_review_rank": chunk[0]["review_rank"],
                "to_review_rank": chunk[-1]["review_rank"],
                "path": str(batch_path),
            }
        )

    manifest = {
        "source_phase_c_json": str(args.phase_c_json),
        "total_rows": len(output_rows),
        "review_rows": len(review_rows),
        "locked_anchor_rows": sum(1 for row in output_rows if row["review_bucket"] == "locked-anchor"),
        "status_counts": dict(sorted(status_counts.items())),
        "review_bucket_counts": dict(sorted(bucket_counts.items())),
        "batch_size": args.batch_size,
        "batch_count": len(batch_manifests),
        "batches": batch_manifests,
    }

    fields = [
        "queue_rank",
        "queue_priority",
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
        "notes",
        "estimated_chinese_center_pos",
        "estimated_chinese_preview_indices",
        "estimated_chinese_preview",
        "nearest_prev_matched_ids",
        "nearest_prev_matched_text",
        "nearest_next_matched_ids",
        "nearest_next_matched_text",
    ]
    review_fields = ["review_rank"] + fields

    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "prompt_template.json", {"prompt_markdown": prompt_template()})
    (args.output_dir / "screening_prompt.md").write_text(prompt_template(), encoding="utf-8")
    write_tsv(args.output_dir / "full_rows.tsv", output_rows, fields)
    write_jsonl(args.output_dir / "full_rows.jsonl", output_rows)
    write_tsv(args.output_dir / "review_rows.tsv", review_rows, review_fields)
    write_jsonl(args.output_dir / "review_rows.jsonl", review_rows)
    print(f"wrote llm screening pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
