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


DEFAULT_PHASE_C_JSON = Path("scratch/phase_c_english_first_forced_rematch_v7_parttail/all_segments.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_gpt52mini_pack_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a focused Phase C pack for GPT-5.2-mini review.")
    parser.add_argument("--mapping-json", type=Path, default=DEFAULT_MAPPING_JSON)
    parser.add_argument("--phase-c-json", type=Path, default=DEFAULT_PHASE_C_JSON)
    parser.add_argument("--english-ocr-root", type=Path, default=DEFAULT_ENGLISH_OCR_ROOT)
    parser.add_argument("--chinese-ocr-root", type=Path, default=DEFAULT_CHINESE_OCR_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=120)
    parser.add_argument("--english-context", type=int, default=2)
    parser.add_argument("--chinese-window-radius", type=int, default=3)
    parser.add_argument("--low-score-threshold", type=float, default=0.22)
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


def nearest_matched_context(clip_rows: list[dict[str, Any]], center: int) -> tuple[str, str, str, str]:
    prev_text = ""
    prev_ids = ""
    next_text = ""
    next_ids = ""
    for idx in range(center - 1, -1, -1):
        row = clip_rows[idx]
        if str(row.get("status") or "") != "unmatched" and str(row.get("current_chinese_text") or "").strip():
            prev_text = str(row.get("current_chinese_text") or "")
            prev_ids = str(row.get("current_chinese_cue_ids") or "")
            break
    for idx in range(center + 1, len(clip_rows)):
        row = clip_rows[idx]
        if str(row.get("status") or "") != "unmatched" and str(row.get("current_chinese_text") or "").strip():
            next_text = str(row.get("current_chinese_text") or "")
            next_ids = str(row.get("current_chinese_cue_ids") or "")
            break
    return prev_ids, prev_text, next_ids, next_text


def prompt_text() -> str:
    return """你会收到 Phase C 英文主骨架匹配队列的一行 JSON。

任务：
1. 如果 `status=unmatched`，请基于英文句子、英文上下文、前后已匹配中文、以及 `estimated_chinese_preview`，判断是否能给出更合理中文。
2. 如果是低分 forced 行，请判断当前 `current_chinese_text` 是否可保留；不行就给出更合理替代，或者明确 no_match。
3. 允许粗糙，但不要明显串句、乱配说话人、或用完全无关片段。

输出 JSON：
{
  "queue_rank": 123,
  "decision": "keep_current_match | replace_match | fill_match | no_match | unsure",
  "confidence": 0.0,
  "suggested_chinese_text": "",
  "reason": ""
}
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
    batch_manifests: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()

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
                status = str(row.get("status") or "unmatched")
                origin = str(row.get("match_origin") or "none")
                score = float(row.get("match_score") or 0.0)

                if status == "unmatched":
                    bucket = "mini-unmatched"
                elif origin.startswith("forced-") and score <= args.low_score_threshold:
                    bucket = "mini-low-forced"
                else:
                    bucket = ""

                ratio = 0.0 if len(clip_english) <= 1 else (local_index - 1) / (len(clip_english) - 1)
                estimated_pos = 0 if not clip_chinese else min(len(clip_chinese) - 1, int(round(ratio * (len(clip_chinese) - 1))))
                preview_indices, preview_text = chinese_preview(clip_chinese, estimated_pos, args.chinese_window_radius)

                item = {
                    "queue_rank": 0,
                    "review_bucket": bucket,
                    "part_name": part_name,
                    "clip_name": clip_name,
                    "english_local_index": local_index,
                    "english_cue_id": cue.cue_id,
                    "start": cue.start,
                    "end": cue.end,
                    "english_text": cue.text,
                    "english_context_text": cue_text_window(clip_english, local_index - 1, args.english_context),
                    "status": status,
                    "match_origin": origin,
                    "match_score": row.get("match_score"),
                    "current_chinese_cue_ids": ",".join(str(item) for item in (row.get("chinese_cue_ids") or [])),
                    "current_chinese_text": str(row.get("chinese_text") or ""),
                    "estimated_chinese_center_pos": estimated_pos,
                    "estimated_chinese_preview_indices": preview_indices,
                    "estimated_chinese_preview": preview_text,
                    "notes": str(row.get("notes") or ""),
                }
                clip_rows.append(item)

            for idx, item in enumerate(clip_rows):
                if not item["review_bucket"]:
                    continue
                prev_ids, prev_text, next_ids, next_text = nearest_matched_context(clip_rows, idx)
                item["nearest_prev_matched_ids"] = prev_ids
                item["nearest_prev_matched_text"] = prev_text
                item["nearest_next_matched_ids"] = next_ids
                item["nearest_next_matched_text"] = next_text
                output_rows.append(item)
                bucket_counts[item["review_bucket"]] += 1

    output_rows.sort(
        key=lambda item: (
            0 if item["review_bucket"] == "mini-unmatched" else 1,
            item["part_name"],
            item["clip_name"],
            int(item["english_local_index"]),
        )
    )
    for queue_rank, row in enumerate(output_rows, start=1):
        row["queue_rank"] = queue_rank

    for batch_index in range(0, len(output_rows), max(args.batch_size, 1)):
        chunk = output_rows[batch_index : batch_index + args.batch_size]
        batch_no = (batch_index // max(args.batch_size, 1)) + 1
        batch_path = args.output_dir / "batches" / f"mini_batch_{batch_no:03d}.jsonl"
        write_jsonl(batch_path, chunk)
        batch_manifests.append(
            {
                "batch_no": batch_no,
                "row_count": len(chunk),
                "from_queue_rank": chunk[0]["queue_rank"],
                "to_queue_rank": chunk[-1]["queue_rank"],
                "path": str(batch_path),
            }
        )

    manifest = {
        "source_phase_c_json": str(args.phase_c_json),
        "row_count": len(output_rows),
        "review_bucket_counts": dict(sorted(bucket_counts.items())),
        "low_score_threshold": args.low_score_threshold,
        "batch_size": args.batch_size,
        "batch_count": len(batch_manifests),
        "batches": batch_manifests,
    }

    fields = [
        "queue_rank",
        "review_bucket",
        "part_name",
        "clip_name",
        "english_local_index",
        "english_cue_id",
        "start",
        "end",
        "english_text",
        "english_context_text",
        "status",
        "match_origin",
        "match_score",
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

    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "prompt_template.json", {"prompt_markdown": prompt_text()})
    (args.output_dir / "screening_prompt.md").write_text(prompt_text(), encoding="utf-8")
    write_tsv(args.output_dir / "mini_rows.tsv", output_rows, fields)
    write_jsonl(args.output_dir / "mini_rows.jsonl", output_rows)
    print(f"wrote mini pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
