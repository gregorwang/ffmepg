from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("scratch/phase_c_llm_screening_pack_v5")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_model_request_batches_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build model-ready request batches from a Phase C screening queue.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--queue-name",
        type=str,
        default="first_pass_match_fix",
        choices=[
            "first_pass_match_fix",
            "remaining_match_fix",
            "unmatched_rich",
            "unmatched_rest",
        ],
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=150)
    parser.add_argument("--rows-per-request", type=int, default=1)
    parser.add_argument(
        "--max-request-char-budget",
        type=int,
        default=0,
        help="Soft cap for one request JSONL line. 0 disables adaptive packing.",
    )
    parser.add_argument(
        "--prompt-style",
        type=str,
        choices=["verbose", "compact"],
        default="verbose",
    )
    parser.add_argument("--preview-char-limit", type=int, default=220)
    parser.add_argument("--context-char-limit", type=int, default=180)
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


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def clipped(text: str, limit: int) -> str:
    normalized = normalize_space(text)
    if limit <= 0 or len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 1, 0)].rstrip() + "..."


def compact_context(text: str, limit: int) -> str:
    normalized = normalize_space(text)
    if not normalized:
        return ""
    return clipped(normalized, limit)


def compact_preview(text: str, limit: int) -> str:
    normalized = normalize_space(text)
    if not normalized:
        return ""
    return clipped(normalized, limit)


def system_prompt(queue_name: str, prompt_style: str) -> str:
    if prompt_style == "compact":
        if "match_fix" in queue_name:
            return "Judge whether current zh matches en. JSON only."
        return "Find zh only if context supports it. JSON only."
    if "match_fix" in queue_name:
        return (
            "You are reviewing bilingual subtitle alignment rows. "
            "Your job is to judge whether the current Chinese match should be kept. "
            "Return strict JSON only."
        )
    return (
        "You are reviewing unmatched bilingual subtitle rows. "
        "Your job is to suggest a Chinese match only when the provided context supports it. "
        "Return strict JSON only."
    )


def compact_payload_row(row: dict[str, Any], preview_char_limit: int, context_char_limit: int) -> dict[str, Any]:
    payload = {
        "id": row.get("row_id") or row.get("focus_rank"),
        "en": normalize_space(str(row.get("english_text") or "")),
        "ctx": compact_context(str(row.get("english_context_text") or ""), context_char_limit),
        "cur": normalize_space(str(row.get("current_chinese_text") or "")),
        "win": compact_preview(str(row.get("estimated_chinese_preview") or ""), preview_char_limit),
        "flag": {
            "status": row.get("status"),
            "origin": row.get("match_origin"),
            "mismatch": row.get("source_clip_mismatch"),
        },
    }
    prev_text = normalize_space(str(row.get("nearest_prev_matched_text") or ""))
    next_text = normalize_space(str(row.get("nearest_next_matched_text") or ""))
    if prev_text:
        payload["prev"] = clipped(prev_text, 80)
    if next_text:
        payload["next"] = clipped(next_text, 80)
    if row.get("risk_score") not in (None, ""):
        payload["risk"] = row.get("risk_score")
    if row.get("notes"):
        payload["note"] = clipped(str(row.get("notes") or ""), 80)
    return payload


def compact_output_schema(row_id: Any) -> dict[str, Any]:
    return {
        "id": row_id,
        "decision": "keep_current_match|reject_current_match|suggest_new_match|no_match|unsure",
        "confidence": 0.0,
        "suggested_chinese_text": "",
        "reason": "",
    }


def user_prompt(queue_name: str, row: dict[str, Any], prompt_style: str, preview_char_limit: int, context_char_limit: int) -> str:
    decision_hint = (
        "Prefer `keep_current_match` or `reject_current_match`."
        if "match_fix" in queue_name
        else "Prefer `suggest_new_match`, `no_match`, or `unsure`."
    )
    schema = {
        "focus_rank": row.get("focus_rank"),
        "decision": "keep_current_match | reject_current_match | suggest_new_match | no_match | unsure",
        "confidence": 0.0,
        "suggested_chinese_text": "",
        "reason": "",
    }
    if prompt_style == "compact":
        payload = compact_payload_row(row, preview_char_limit, context_char_limit)
        compact_schema = compact_output_schema(payload["id"])
        return (
            f"Task: {decision_hint}\n"
            f"Input:{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n"
            f"Output:{json.dumps(compact_schema, ensure_ascii=False, separators=(',', ':'))}"
        )
    payload = {
        "queue_name": queue_name,
        "focus_rank": row.get("focus_rank"),
        "part_name": row.get("part_name"),
        "clip_name": row.get("clip_name"),
        "english_local_index": row.get("english_local_index"),
        "english_cue_id": row.get("english_cue_id"),
        "english_text": row.get("english_text"),
        "english_context_text": row.get("english_context_text"),
        "status": row.get("status"),
        "match_origin": row.get("match_origin"),
        "match_score": row.get("match_score"),
        "source_clip": row.get("source_clip"),
        "source_clip_mismatch": row.get("source_clip_mismatch"),
        "current_chinese_cue_ids": row.get("current_chinese_cue_ids"),
        "current_chinese_text": row.get("current_chinese_text"),
        "estimated_chinese_preview_indices": row.get("estimated_chinese_preview_indices"),
        "estimated_chinese_preview": row.get("estimated_chinese_preview"),
        "nearest_prev_matched_text": row.get("nearest_prev_matched_text"),
        "nearest_next_matched_text": row.get("nearest_next_matched_text"),
        "risk_score": row.get("risk_score"),
        "value_score": row.get("value_score"),
        "notes": row.get("notes"),
    }
    return (
        f"Task: review one Phase C row. {decision_hint}\n\n"
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        f"Return JSON only with this shape:\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
    )


def grouped_user_prompt(
    queue_name: str,
    rows: list[dict[str, Any]],
    prompt_style: str,
    preview_char_limit: int,
    context_char_limit: int,
) -> str:
    decision_hint = (
        "Prefer `keep_current_match` or `reject_current_match`."
        if "match_fix" in queue_name
        else "Prefer `suggest_new_match`, `no_match`, or `unsure`."
    )
    if prompt_style == "compact":
        payload_rows = [compact_payload_row(row, preview_char_limit, context_char_limit) for row in rows]
        output_schema = {"rows": [compact_output_schema(payload_row["id"]) for payload_row in payload_rows]}
        return (
            f"Task: review {len(rows)} rows. {decision_hint}\n"
            f"Input:{json.dumps({'rows': payload_rows}, ensure_ascii=False, separators=(',', ':'))}\n"
            f"Output:{json.dumps(output_schema, ensure_ascii=False, separators=(',', ':'))}"
        )

    payload = []
    for row in rows:
        payload.append(
            {
                "id": row.get("row_id"),
                "focus_rank": row.get("focus_rank"),
                "part_name": row.get("part_name"),
                "clip_name": row.get("clip_name"),
                "english_cue_id": row.get("english_cue_id"),
                "english_text": row.get("english_text"),
                "english_context_text": row.get("english_context_text"),
                "status": row.get("status"),
                "match_origin": row.get("match_origin"),
                "match_score": row.get("match_score"),
                "source_clip_mismatch": row.get("source_clip_mismatch"),
                "current_chinese_text": row.get("current_chinese_text"),
                "estimated_chinese_preview": row.get("estimated_chinese_preview"),
                "nearest_prev_matched_text": row.get("nearest_prev_matched_text"),
                "nearest_next_matched_text": row.get("nearest_next_matched_text"),
                "risk_score": row.get("risk_score"),
                "notes": row.get("notes"),
            }
        )
    output_schema = {
        "rows": [
            {
                "id": row.get("row_id"),
                "decision": "keep_current_match | reject_current_match | suggest_new_match | no_match | unsure",
                "confidence": 0.0,
                "suggested_chinese_text": "",
                "reason": "",
            }
            for row in rows
        ]
    }
    return (
        f"Task: review {len(rows)} Phase C rows. {decision_hint}\n\n"
        f"Input JSON:\n{json.dumps({'rows': payload}, ensure_ascii=False, indent=2)}\n\n"
        f"Return JSON only with this shape:\n{json.dumps(output_schema, ensure_ascii=False, indent=2)}"
    )


def build_request_payload(
    queue_name: str,
    group: list[dict[str, Any]],
    prompt_style: str,
    preview_char_limit: int,
    context_char_limit: int,
    bundle_no: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prepared_group: list[dict[str, Any]] = []
    for index, source_row in enumerate(group, start=1):
        row = dict(source_row)
        row["row_id"] = f"r{index:02d}"
        prepared_group.append(row)

    if len(prepared_group) == 1:
        row = prepared_group[0]
        focus_rank = int(row.get("focus_rank") or 0)
        custom_id = f"{queue_name}:{focus_rank:05d}:{row['part_name']}:{row['english_cue_id']}"
        request = {
            "custom_id": custom_id,
            "messages": [
                {"role": "system", "content": system_prompt(queue_name, prompt_style)},
                {
                    "role": "user",
                    "content": user_prompt(
                        queue_name,
                        row,
                        prompt_style,
                        preview_char_limit,
                        context_char_limit,
                    ),
                },
            ],
            "metadata": {
                "queue_name": queue_name,
                "focus_rank": focus_rank,
                "part_name": row["part_name"],
                "clip_name": row["clip_name"],
                "english_cue_id": row["english_cue_id"],
                "rows_per_request": 1,
                "from_focus_rank": focus_rank,
                "to_focus_rank": focus_rank,
            },
        }
        return request, prepared_group

    custom_id = f"{queue_name}:bundle:{bundle_no:05d}"
    request = {
        "custom_id": custom_id,
        "messages": [
            {"role": "system", "content": system_prompt(queue_name, prompt_style)},
            {
                "role": "user",
                "content": grouped_user_prompt(
                    queue_name,
                    prepared_group,
                    prompt_style,
                    preview_char_limit,
                    context_char_limit,
                ),
            },
        ],
        "metadata": {
            "queue_name": queue_name,
            "rows_per_request": len(prepared_group),
            "from_focus_rank": int(prepared_group[0].get("focus_rank") or 0),
            "to_focus_rank": int(prepared_group[-1].get("focus_rank") or 0),
        },
    }
    return request, prepared_group


def request_char_length(request: dict[str, Any]) -> int:
    return len(json.dumps(request, ensure_ascii=False))


def pack_rows(
    rows: list[dict[str, Any]],
    queue_name: str,
    rows_per_request: int,
    prompt_style: str,
    preview_char_limit: int,
    context_char_limit: int,
    max_request_char_budget: int,
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    groups: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    max_rows = max(rows_per_request, 1)
    index = 0
    bundle_no = 1
    while index < len(rows):
        group = [rows[index]]
        best_request, best_prepared_group = build_request_payload(
            queue_name,
            group,
            prompt_style,
            preview_char_limit,
            context_char_limit,
            bundle_no,
        )
        if max_request_char_budget > 0 and request_char_length(best_request) > max_request_char_budget:
            groups.append((best_request, best_prepared_group))
            index += 1
            bundle_no += 1
            continue

        next_index = index + 1
        while next_index < len(rows) and len(group) < max_rows:
            candidate_group = rows[index : next_index + 1]
            candidate_request, candidate_prepared_group = build_request_payload(
                queue_name,
                candidate_group,
                prompt_style,
                preview_char_limit,
                context_char_limit,
                bundle_no,
            )
            if max_request_char_budget > 0 and request_char_length(candidate_request) > max_request_char_budget:
                break
            best_request = candidate_request
            best_prepared_group = candidate_prepared_group
            group = candidate_group
            next_index += 1

        groups.append((best_request, best_prepared_group))
        index += len(best_prepared_group)
        bundle_no += 1

    return groups


def main() -> None:
    args = parse_args()
    queue_path = args.input_dir / f"{args.queue_name}_rows.jsonl"
    rows = load_jsonl(queue_path)
    input_manifest = load_json(args.input_dir / "manifest.json")

    requests: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    request_focus_spans: list[tuple[int, int]] = []

    rows_per_request = max(int(args.rows_per_request), 1)
    packed_requests = pack_rows(
        rows,
        args.queue_name,
        rows_per_request,
        args.prompt_style,
        args.preview_char_limit,
        args.context_char_limit,
        max(int(args.max_request_char_budget), 0),
    )
    for request, prepared_group in packed_requests:
        requests.append(request)
        request_focus_spans.append(
            (
                int(prepared_group[0].get("focus_rank") or 0),
                int(prepared_group[-1].get("focus_rank") or 0),
            )
        )
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

    batch_manifests: list[dict[str, Any]] = []
    queue_output_dir = args.output_dir / args.queue_name
    for offset in range(0, len(requests), max(args.batch_size, 1)):
        chunk = requests[offset : offset + args.batch_size]
        batch_no = (offset // max(args.batch_size, 1)) + 1
        path = queue_output_dir / "batches" / f"{args.queue_name}_requests_{batch_no:03d}.jsonl"
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
        "source_input_dir": str(args.input_dir),
        "source_manifest_batch_size": input_manifest.get("batch_size"),
        "queue_name": args.queue_name,
        "request_count": len(requests),
        "batch_size": args.batch_size,
        "rows_per_request": rows_per_request,
        "max_request_char_budget": max(int(args.max_request_char_budget), 0),
        "prompt_style": args.prompt_style,
        "preview_char_limit": args.preview_char_limit,
        "context_char_limit": args.context_char_limit,
        "batch_count": len(batch_manifests),
        "batches": batch_manifests,
    }
    write_json(queue_output_dir / "manifest.json", manifest)
    (queue_output_dir / "SYSTEM_PROMPT.txt").write_text(system_prompt(args.queue_name, args.prompt_style), encoding="utf-8")
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
    print(f"wrote model request batches -> {queue_output_dir}")


if __name__ == "__main__":
    main()
