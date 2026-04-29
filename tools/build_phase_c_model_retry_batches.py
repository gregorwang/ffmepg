from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_REQUEST_ROOT = Path("scratch/phase_c_model_request_batches_v1")
DEFAULT_INGEST_ROOT = Path("scratch/phase_c_model_response_ingest_v1")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_model_retry_batches_v1")
DEFAULT_POINTER_PATH = Path("scratch/PHASE_C_CURRENT_MODEL_RETRY_REQUESTS.txt")
VALID_DECISIONS = {
    "keep_current_match",
    "reject_current_match",
    "suggest_new_match",
    "no_match",
    "unsure",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build next-pass retry request batches from Phase C model ingest outputs.")
    parser.add_argument("--request-root", type=Path, default=DEFAULT_REQUEST_ROOT)
    parser.add_argument("--ingest-root", type=Path, default=DEFAULT_INGEST_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--queue-names", nargs="+")
    parser.add_argument("--output-queue-name", type=str, help="Optional explicit output queue name, e.g. retry_round2.")
    parser.add_argument("--batch-size", type=int, default=150)
    parser.add_argument("--confidence-threshold", type=float, default=0.6)
    parser.add_argument("--skip-missing", action="store_true")
    parser.add_argument("--update-current-pointer", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_source_pack_rows(source_pack_dir: Path) -> dict[str, dict[str, Any]]:
    source_rows: dict[str, dict[str, Any]] = {}
    tsv_path = source_pack_dir / "mini_rows.tsv"
    jsonl_path = source_pack_dir / "mini_rows.jsonl"
    rows: list[dict[str, Any]] = []
    if tsv_path.exists():
        rows = load_tsv(tsv_path)
    elif jsonl_path.exists():
        rows = load_jsonl(jsonl_path)
    for row in rows:
        queue_rank = str(row.get("queue_rank") or "").strip()
        focus_rank = str(row.get("focus_rank") or "").strip()
        english_cue_id = str(row.get("english_cue_id") or "").strip()
        if queue_rank:
            source_rows[queue_rank] = row
        if focus_rank:
            source_rows.setdefault(focus_rank, row)
        if english_cue_id:
            source_rows.setdefault(english_cue_id, row)
    return source_rows


def reconstruct_original_user_content(source_row: dict[str, Any], prompt_markdown: str) -> str:
    payload = {
        "queue_rank": source_row.get("queue_rank"),
        "review_bucket": source_row.get("review_bucket"),
        "part_name": source_row.get("part_name"),
        "clip_name": source_row.get("clip_name"),
        "english_local_index": source_row.get("english_local_index"),
        "english_cue_id": source_row.get("english_cue_id"),
        "start": source_row.get("start"),
        "end": source_row.get("end"),
        "english_text": source_row.get("english_text"),
        "english_context_text": source_row.get("english_context_text"),
        "status": source_row.get("status"),
        "match_origin": source_row.get("match_origin"),
        "match_score": source_row.get("match_score"),
        "current_chinese_cue_ids": source_row.get("current_chinese_cue_ids"),
        "current_chinese_text": source_row.get("current_chinese_text"),
        "estimated_chinese_center_pos": source_row.get("estimated_chinese_center_pos"),
        "estimated_chinese_preview_indices": source_row.get("estimated_chinese_preview_indices"),
        "estimated_chinese_preview": source_row.get("estimated_chinese_preview"),
        "nearest_prev_matched_ids": source_row.get("nearest_prev_matched_ids"),
        "nearest_prev_matched_text": source_row.get("nearest_prev_matched_text"),
        "nearest_next_matched_ids": source_row.get("nearest_next_matched_ids"),
        "nearest_next_matched_text": source_row.get("nearest_next_matched_text"),
        "notes": source_row.get("notes"),
    }
    return f"{prompt_markdown}\n\nInput JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


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


def write_pointer(path: Path, target_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(target_dir), encoding="utf-8")


def detect_queue_names(ingest_root: Path, explicit_queue_names: list[str] | None) -> list[str]:
    if explicit_queue_names:
        return list(explicit_queue_names)
    detected: list[str] = []
    for queue_dir in sorted(path for path in ingest_root.iterdir() if path.is_dir()):
        if (queue_dir / "manifest.json").exists():
            detected.append(queue_dir.name)
    if not detected:
        raise SystemExit(f"no ingest queue dirs found under: {ingest_root}")
    return detected


def retry_round_number(queue_name: str) -> int | None:
    match = re.fullmatch(r"retry_round(\d+)", (queue_name or "").strip().lower())
    return int(match.group(1)) if match else None


def resolve_output_queue_name(queue_names: list[str], explicit_output_queue_name: str | None) -> str:
    if explicit_output_queue_name:
        return explicit_output_queue_name
    retry_numbers = [number for number in (retry_round_number(queue_name) for queue_name in queue_names) if number is not None]
    if retry_numbers:
        return f"retry_round{max(retry_numbers) + 1}"
    return "retry_round1"


def confidence_value(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_request_map(request_root: Path, queue_names: list[str]) -> dict[str, dict[str, Any]]:
    request_map: dict[str, dict[str, Any]] = {}
    for queue_name in queue_names:
        batch_dir = request_root / queue_name / "batches"
        for path in sorted(batch_dir.glob("*.jsonl")):
            for row in load_jsonl(path):
                custom_id = str(row.get("custom_id") or "")
                if custom_id:
                    request_map[custom_id] = row
    return request_map


def request_row_key(request_custom_id: str, row_id: str) -> str:
    return f"{request_custom_id}::{row_id}" if row_id else request_custom_id


def retry_system_prompt() -> str:
    return (
        "You are doing a second-pass adjudication on bilingual subtitle alignment rows. "
        "Use the prior model output only as a hint, not as ground truth. "
        "Return strict JSON only."
    )


def build_retry_user_content(original_user: str, retry_reason: str, prior_payload: dict[str, Any]) -> str:
    return (
        f"{original_user}\n\n"
        "Second-pass adjudication instructions:\n"
        "- Re-evaluate from scratch.\n"
        "- Use the previous model result only as weak evidence.\n"
        "- If previous output was malformed, missing, or low-confidence, ignore it if needed.\n"
        f"- Retry reason: {retry_reason}\n\n"
        f"Previous model result:\n{json.dumps(prior_payload, ensure_ascii=False, indent=2)}"
    )


def make_retry_record(
    *,
    queue_name: str,
    original_request: dict[str, Any] | None,
    original_index_row: dict[str, str] | None,
    source_row: dict[str, Any] | None,
    prompt_markdown: str,
    original_custom_id: str,
    original_request_custom_id: str,
    original_row_id: str,
    retry_reason: str,
    prior_payload: dict[str, Any],
) -> dict[str, Any] | None:
    if original_request is None:
        if source_row is None:
            return None
        original_user = reconstruct_original_user_content(source_row, prompt_markdown)
        original_request = {
            "custom_id": original_request_custom_id,
            "messages": [{"role": "user", "content": original_user}],
            "metadata": dict(source_row),
        }
    messages = list(original_request.get("messages") or [])
    original_user = ""
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "user":
            original_user = str(message.get("content") or "")
            break
    if not original_user:
        return None

    if original_index_row is None:
        metadata = dict(original_request.get("metadata") or {})
        part_name = str(metadata.get("part_name") or "")
        clip_name = str(metadata.get("clip_name") or "")
        english_cue_id = str(metadata.get("english_cue_id") or "")
        focus_rank = int(metadata.get("focus_rank") or 0)
        status = ""
        match_origin = ""
        source_clip_mismatch = ""
        current_chinese_text = ""
    else:
        part_name = str(original_index_row.get("part_name") or "")
        clip_name = str(original_index_row.get("clip_name") or "")
        english_cue_id = str(original_index_row.get("english_cue_id") or "")
        focus_rank = int(original_index_row.get("focus_rank") or 0)
        status = str(original_index_row.get("status") or "")
        match_origin = str(original_index_row.get("match_origin") or "")
        source_clip_mismatch = str(original_index_row.get("source_clip_mismatch") or "")
        current_chinese_text = str(original_index_row.get("current_chinese_text") or "")

    return {
        "source_queue_name": queue_name,
        "original_custom_id": original_custom_id,
        "original_request_custom_id": original_request_custom_id,
        "original_row_id": original_row_id,
        "focus_rank": focus_rank,
        "part_name": part_name,
        "clip_name": clip_name,
        "english_cue_id": english_cue_id,
        "status": status,
        "match_origin": match_origin,
        "source_clip_mismatch": source_clip_mismatch,
        "current_chinese_text": current_chinese_text,
        "retry_reason": retry_reason,
        "prior_payload": prior_payload,
        "original_user_content": original_user,
        "original_request": original_request,
    }


def main() -> None:
    args = parse_args()
    queue_names = detect_queue_names(args.ingest_root, args.queue_names)
    output_queue_name = resolve_output_queue_name(queue_names, args.output_queue_name)
    request_map = load_request_map(args.request_root, list(queue_names))
    source_pack_dir = args.request_root.parent
    source_rows_by_key = load_source_pack_rows(source_pack_dir)
    prompt_markdown = ""
    prompt_template_path = source_pack_dir / "prompt_template.json"
    if prompt_template_path.exists():
        try:
            prompt_markdown = str(load_json(prompt_template_path).get("prompt_markdown") or "")
        except Exception:
            prompt_markdown = ""
    retry_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []

    for queue_name in queue_names:
        request_index_path = args.request_root / queue_name / "request_index.tsv"
        request_index = load_tsv(request_index_path)
        request_index_by_key = {
            request_row_key(
                str(row.get("request_custom_id") or row.get("custom_id") or ""),
                str(row.get("row_id") or ""),
            ): row
            for row in request_index
        }

        queue_ingest_dir = args.ingest_root / queue_name
        normalized_rows = load_tsv(queue_ingest_dir / "normalized_responses.tsv") if (queue_ingest_dir / "normalized_responses.tsv").exists() else []
        unresolved_rows = load_tsv(queue_ingest_dir / "unresolved_responses.tsv") if (queue_ingest_dir / "unresolved_responses.tsv").exists() else []
        missing_rows = [] if args.skip_missing else (load_tsv(queue_ingest_dir / "missing_requests.tsv") if (queue_ingest_dir / "missing_requests.tsv").exists() else [])

        for row in normalized_rows:
            original_custom_id = str(row.get("custom_id") or "")
            original_request_custom_id = str(row.get("request_custom_id") or original_custom_id)
            original_row_id = str(row.get("row_id") or "")
            decision = str(row.get("decision") or "").strip().lower()
            confidence = confidence_value(str(row.get("confidence") or ""))
            suggested = str(row.get("suggested_chinese_text") or "").strip()
            retry_reason = ""

            if decision not in VALID_DECISIONS:
                retry_reason = "invalid-decision"
            elif decision == "unsure":
                retry_reason = "model-unsure"
            elif decision == "suggest_new_match" and not suggested:
                retry_reason = "missing-suggestion-text"
            elif confidence is not None and confidence < args.confidence_threshold:
                retry_reason = "low-confidence"

            if not retry_reason:
                continue

            retry_record = make_retry_record(
                queue_name=queue_name,
                original_request=request_map.get(original_request_custom_id),
                original_index_row=request_index_by_key.get(request_row_key(original_request_custom_id, original_row_id)),
                source_row=source_rows_by_key.get(original_row_id) or source_rows_by_key.get(original_request_custom_id) or source_rows_by_key.get(str(row.get("focus_rank") or "")) or source_rows_by_key.get(str(row.get("english_cue_id") or "")),
                prompt_markdown=prompt_markdown,
                original_custom_id=original_custom_id,
                original_request_custom_id=original_request_custom_id,
                original_row_id=original_row_id,
                retry_reason=retry_reason,
                prior_payload={
                    "decision": decision,
                    "confidence": confidence,
                    "suggested_chinese_text": suggested,
                    "reason": str(row.get("reason") or ""),
                    "raw_text": str(row.get("raw_text") or ""),
                },
            )
            if retry_record is None:
                skipped_rows.append(
                    {
                        "source_queue_name": queue_name,
                        "original_custom_id": original_custom_id,
                        "retry_reason": retry_reason,
                        "skip_reason": "original-request-not-found",
                    }
                )
                continue
            retry_rows.append(retry_record)

        for row in unresolved_rows:
            original_custom_id = str(row.get("custom_id") or "")
            original_request_custom_id = str(row.get("request_custom_id") or original_custom_id)
            original_row_id = str(row.get("row_id") or "")
            retry_record = make_retry_record(
                queue_name=queue_name,
                original_request=request_map.get(original_request_custom_id),
                original_index_row=request_index_by_key.get(request_row_key(original_request_custom_id, original_row_id)),
                source_row=source_rows_by_key.get(original_row_id) or source_rows_by_key.get(original_request_custom_id) or source_rows_by_key.get(str(row.get("focus_rank") or "")) or source_rows_by_key.get(str(row.get("english_cue_id") or "")),
                prompt_markdown=prompt_markdown,
                original_custom_id=original_custom_id,
                original_request_custom_id=original_request_custom_id,
                original_row_id=original_row_id,
                retry_reason=str(row.get("error") or "unresolved-response"),
                prior_payload={
                    "error": str(row.get("error") or ""),
                    "raw_text": str(row.get("raw_text") or ""),
                },
            )
            if retry_record is None:
                skipped_rows.append(
                    {
                        "source_queue_name": queue_name,
                        "original_custom_id": original_custom_id,
                        "retry_reason": str(row.get("error") or "unresolved-response"),
                        "skip_reason": "original-request-not-found",
                    }
                )
                continue
            retry_rows.append(retry_record)

        for row in missing_rows:
            original_custom_id = str(row.get("custom_id") or "")
            original_request_custom_id = str(row.get("request_custom_id") or original_custom_id)
            original_row_id = str(row.get("row_id") or "")
            retry_record = make_retry_record(
                queue_name=queue_name,
                original_request=request_map.get(original_request_custom_id),
                original_index_row=row,
                source_row=source_rows_by_key.get(original_row_id) or source_rows_by_key.get(original_request_custom_id) or source_rows_by_key.get(str(row.get("focus_rank") or "")) or source_rows_by_key.get(str(row.get("english_cue_id") or "")),
                prompt_markdown=prompt_markdown,
                original_custom_id=original_custom_id,
                original_request_custom_id=original_request_custom_id,
                original_row_id=original_row_id,
                retry_reason="missing-response",
                prior_payload={
                    "error": "missing-response",
                },
            )
            if retry_record is None:
                skipped_rows.append(
                    {
                        "source_queue_name": queue_name,
                        "original_custom_id": original_custom_id,
                        "retry_reason": "missing-response",
                        "skip_reason": "original-request-not-found",
                    }
                )
                continue
            retry_rows.append(retry_record)

    retry_rows.sort(
        key=lambda row: (
            row["source_queue_name"],
            row["part_name"],
            row["focus_rank"],
            row["english_cue_id"],
        )
    )

    requests: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    for index, row in enumerate(retry_rows, start=1):
        original_request = dict(row["original_request"])
        retry_custom_id = (
            f"{output_queue_name}:{index:05d}:{row['source_queue_name']}:{row['part_name']}:{row['english_cue_id']}"
        )
        request = {
            "custom_id": retry_custom_id,
            "messages": [
                {"role": "system", "content": retry_system_prompt()},
                {
                    "role": "user",
                    "content": build_retry_user_content(
                        str(row["original_user_content"]),
                        str(row["retry_reason"]),
                        dict(row["prior_payload"]),
                    ),
                },
            ],
            "metadata": {
                "queue_name": output_queue_name,
                "source_queue_name": row["source_queue_name"],
                "original_custom_id": row["original_custom_id"],
                "original_request_custom_id": row["original_request_custom_id"],
                "original_row_id": row["original_row_id"],
                "focus_rank": row["focus_rank"],
                "part_name": row["part_name"],
                "clip_name": row["clip_name"],
                "english_cue_id": row["english_cue_id"],
                "retry_reason": row["retry_reason"],
            },
        }
        requests.append(request)
        index_rows.append(
            {
                "custom_id": retry_custom_id,
                "retry_rank": index,
                "source_queue_name": row["source_queue_name"],
                "original_custom_id": row["original_custom_id"],
                "original_request_custom_id": row["original_request_custom_id"],
                "original_row_id": row["original_row_id"],
                "focus_rank": row["focus_rank"],
                "part_name": row["part_name"],
                "clip_name": row["clip_name"],
                "english_cue_id": row["english_cue_id"],
                "status": row["status"],
                "match_origin": row["match_origin"],
                "source_clip_mismatch": row["source_clip_mismatch"],
                "current_chinese_text": row["current_chinese_text"],
                "retry_reason": row["retry_reason"],
            }
        )

    batch_manifests: list[dict[str, Any]] = []
    output_queue_dir = args.output_dir / output_queue_name
    for offset in range(0, len(requests), max(args.batch_size, 1)):
        chunk = requests[offset : offset + args.batch_size]
        batch_no = (offset // max(args.batch_size, 1)) + 1
        path = output_queue_dir / "batches" / f"{output_queue_name}_requests_{batch_no:03d}.jsonl"
        write_jsonl(path, chunk)
        batch_manifests.append(
            {
                "batch_no": batch_no,
                "request_count": len(chunk),
                "from_retry_rank": index_rows[offset]["retry_rank"],
                "to_retry_rank": index_rows[offset + len(chunk) - 1]["retry_rank"],
                "path": str(path),
            }
        )

    retry_reason_counts: dict[str, int] = {}
    source_queue_counts: dict[str, int] = {}
    for row in index_rows:
        retry_reason = str(row.get("retry_reason") or "")
        source_queue_name = str(row.get("source_queue_name") or "")
        retry_reason_counts[retry_reason] = retry_reason_counts.get(retry_reason, 0) + 1
        source_queue_counts[source_queue_name] = source_queue_counts.get(source_queue_name, 0) + 1

    manifest = {
        "source_request_root": str(args.request_root),
        "source_ingest_root": str(args.ingest_root),
        "queue_name": output_queue_name,
        "source_queues": list(queue_names),
        "request_count": len(requests),
        "batch_size": args.batch_size,
        "batch_count": len(batch_manifests),
        "confidence_threshold": args.confidence_threshold,
        "skip_missing": args.skip_missing,
        "retry_reason_counts": dict(sorted(retry_reason_counts.items())),
        "source_queue_counts": dict(sorted(source_queue_counts.items())),
        "skipped_row_count": len(skipped_rows),
        "batches": batch_manifests,
    }
    write_json(output_queue_dir / "manifest.json", manifest)
    (output_queue_dir / "SYSTEM_PROMPT.txt").write_text(retry_system_prompt(), encoding="utf-8")
    write_tsv(
        output_queue_dir / "request_index.tsv",
        index_rows,
        [
            "custom_id",
            "retry_rank",
            "source_queue_name",
            "original_custom_id",
            "original_request_custom_id",
            "original_row_id",
            "focus_rank",
            "part_name",
            "clip_name",
            "english_cue_id",
            "status",
            "match_origin",
            "source_clip_mismatch",
            "current_chinese_text",
            "retry_reason",
        ],
    )
    write_tsv(
        output_queue_dir / "skipped_rows.tsv",
        skipped_rows,
        [
            "source_queue_name",
            "original_custom_id",
            "retry_reason",
            "skip_reason",
        ],
    )
    if args.update_current_pointer:
        write_pointer(DEFAULT_POINTER_PATH, output_queue_dir)
    print(f"wrote model retry batches -> {output_queue_dir}")


if __name__ == "__main__":
    main()
