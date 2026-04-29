from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_phase_c_model_request_batches import load_jsonl, main as _unused_main
from build_phase_c_model_request_batches import write_json
from build_phase_c_model_request_batches import (
    load_json,
    pack_rows,
    request_char_length,
    system_prompt,
    write_jsonl,
    write_tsv,
)


DEFAULT_INPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v5")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_model_request_batches_v7_mixedfast")
DEFAULT_PROFILE = Path("scratch/phase_c_model_request_profiles_v1/mixedfast_7500.json")
QUEUE_ORDER = [
    "first_pass_match_fix",
    "remaining_match_fix",
    "unmatched_rich",
    "unmatched_rest",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a multi-queue Phase C request root from queue-specific profiles.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--profile-json", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=150)
    return parser.parse_args()


def build_queue(
    input_dir: Path,
    queue_name: str,
    output_dir: Path,
    batch_size: int,
    profile: dict[str, Any],
) -> dict[str, Any]:
    rows = load_jsonl(input_dir / f"{queue_name}_rows.jsonl")
    rows_per_request = max(int(profile.get("rows_per_request", 1)), 1)
    prompt_style = str(profile.get("prompt_style", "compact"))
    preview_char_limit = int(profile.get("preview_char_limit", 100))
    context_char_limit = int(profile.get("context_char_limit", 80))
    max_request_char_budget = max(int(profile.get("max_request_char_budget", 0)), 0)

    packed_requests = pack_rows(
        rows,
        queue_name,
        rows_per_request,
        prompt_style,
        preview_char_limit,
        context_char_limit,
        max_request_char_budget,
    )

    requests: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    request_focus_spans: list[tuple[int, int]] = []
    request_lengths: list[int] = []

    for request, prepared_group in packed_requests:
        requests.append(request)
        request_focus_spans.append(
            (
                int(prepared_group[0].get("focus_rank") or 0),
                int(prepared_group[-1].get("focus_rank") or 0),
            )
        )
        request_lengths.append(request_char_length(request))
        for row in prepared_group:
            index_rows.append(
                {
                    "custom_id": request["custom_id"],
                    "request_custom_id": request["custom_id"],
                    "row_id": row["row_id"],
                    "focus_rank": int(row.get("focus_rank") or 0),
                    "part_name": row["part_name"],
                    "clip_name": row["clip_name"],
                    "english_cue_id": row["english_cue_id"],
                    "status": row["status"],
                    "match_origin": row["match_origin"],
                    "source_clip_mismatch": row["source_clip_mismatch"],
                    "current_chinese_text": row["current_chinese_text"],
                }
            )

    queue_output_dir = output_dir / queue_name
    batch_manifests: list[dict[str, Any]] = []
    for offset in range(0, len(requests), max(batch_size, 1)):
        chunk = requests[offset : offset + batch_size]
        batch_no = (offset // max(batch_size, 1)) + 1
        path = queue_output_dir / "batches" / f"{queue_name}_requests_{batch_no:03d}.jsonl"
        write_jsonl(path, chunk)
        span_start = request_focus_spans[offset][0]
        span_end = request_focus_spans[offset + len(chunk) - 1][1]
        batch_manifests.append(
            {
                "batch_no": batch_no,
                "request_count": len(chunk),
                "from_focus_rank": span_start,
                "to_focus_rank": span_end,
                "path": str(path),
            }
        )

    manifest = {
        "source_input_dir": str(input_dir),
        "queue_name": queue_name,
        "request_count": len(requests),
        "batch_size": batch_size,
        "rows_per_request": rows_per_request,
        "max_request_char_budget": max_request_char_budget,
        "prompt_style": prompt_style,
        "preview_char_limit": preview_char_limit,
        "context_char_limit": context_char_limit,
        "batch_count": len(batch_manifests),
        "avg_request_chars": round(sum(request_lengths) / len(request_lengths), 1) if request_lengths else 0.0,
        "max_request_chars": max(request_lengths) if request_lengths else 0,
        "batches": batch_manifests,
    }
    write_json(queue_output_dir / "manifest.json", manifest)
    (queue_output_dir / "SYSTEM_PROMPT.txt").write_text(system_prompt(queue_name, prompt_style), encoding="utf-8")
    write_tsv(
        queue_output_dir / "request_index.tsv",
        index_rows,
        [
            "custom_id",
            "request_custom_id",
            "row_id",
            "focus_rank",
            "part_name",
            "clip_name",
            "english_cue_id",
            "status",
            "match_origin",
            "source_clip_mismatch",
            "current_chinese_text",
        ],
    )
    return manifest


def main() -> None:
    args = parse_args()
    profile_doc = load_json(args.profile_json)
    input_manifest = load_json(args.input_dir / "manifest.json")
    queue_profiles = profile_doc.get("queue_profiles") or {}

    summary_rows: list[dict[str, Any]] = []
    total_request_count = 0
    total_avg_chars_weight = 0.0
    total_batch_count = 0

    for queue_name in QUEUE_ORDER:
        profile = queue_profiles.get(queue_name)
        if not isinstance(profile, dict):
            raise SystemExit(f"missing queue profile for: {queue_name}")
        manifest = build_queue(
            args.input_dir,
            queue_name,
            args.output_dir,
            args.batch_size,
            profile,
        )
        total_request_count += int(manifest["request_count"])
        total_batch_count += int(manifest["batch_count"])
        total_avg_chars_weight += float(manifest["avg_request_chars"]) * int(manifest["request_count"])
        summary_rows.append(
            {
                "queue_name": queue_name,
                "request_count": manifest["request_count"],
                "avg_request_chars": manifest["avg_request_chars"],
                "max_request_chars": manifest["max_request_chars"],
                "rows_per_request": manifest["rows_per_request"],
                "max_request_char_budget": manifest["max_request_char_budget"],
                "prompt_style": manifest["prompt_style"],
                "preview_char_limit": manifest["preview_char_limit"],
                "context_char_limit": manifest["context_char_limit"],
            }
        )

    root_manifest = {
        "source_input_dir": str(args.input_dir),
        "source_manifest_batch_size": input_manifest.get("batch_size"),
        "profile_json": str(args.profile_json),
        "request_root": str(args.output_dir),
        "queue_count": len(summary_rows),
        "total_request_count": total_request_count,
        "total_batch_count": total_batch_count,
        "weighted_avg_request_chars": round(total_avg_chars_weight / total_request_count, 1) if total_request_count else 0.0,
        "queue_summaries": summary_rows,
    }
    write_json(args.output_dir / "manifest.json", root_manifest)
    write_tsv(
        args.output_dir / "queue_summary.tsv",
        summary_rows,
        [
            "queue_name",
            "request_count",
            "avg_request_chars",
            "max_request_chars",
            "rows_per_request",
            "max_request_char_budget",
            "prompt_style",
            "preview_char_limit",
            "context_char_limit",
        ],
    )
    print(f"wrote model request root -> {args.output_dir}")


if __name__ == "__main__":
    main()
