from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_REQUEST_ROOT = Path("scratch/phase_c_model_request_batches_v1")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_model_response_ingest_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest model response JSONL files for Phase C screening queues.")
    parser.add_argument("--request-root", type=Path, default=DEFAULT_REQUEST_ROOT)
    parser.add_argument("--queue-name", type=str, required=True)
    parser.add_argument("--response-dir", type=Path, required=True, help="Directory containing one or more response JSONL files.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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


def union_fieldnames(rows: list[dict[str, Any]], preferred: list[str]) -> list[str]:
    discovered: list[str] = []
    seen = set(preferred)
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                discovered.append(key)
    return preferred + discovered


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def try_parse_json_text(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        snippet = text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


def extract_message_text(item: dict[str, Any]) -> str:
    if isinstance(item.get("output_text"), str):
        return str(item["output_text"])
    if isinstance(item.get("content"), str):
        return str(item["content"])
    response = item.get("response")
    if isinstance(response, dict):
        if isinstance(response.get("output_text"), str):
            return str(response["output_text"])
        outputs = response.get("output")
        if isinstance(outputs, list):
            chunks: list[str] = []
            for output in outputs:
                if not isinstance(output, dict):
                    continue
                contents = output.get("content")
                if isinstance(contents, list):
                    for content in contents:
                        if isinstance(content, dict) and isinstance(content.get("text"), str):
                            chunks.append(str(content["text"]))
            if chunks:
                return "\n".join(chunks)
        choices = response.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    chunks = []
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            chunks.append(str(part["text"]))
                    if chunks:
                        return "\n".join(chunks)
    return ""


def normalize_response(item: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None, str]:
    custom_id = item.get("custom_id")
    if not isinstance(custom_id, str):
        custom_id = None

    direct_payload = None
    if isinstance(item.get("decision"), str):
        direct_payload = item
    elif isinstance(item.get("output"), dict):
        direct_payload = item["output"]

    raw_text = ""
    parsed = None
    if direct_payload is not None:
        parsed = direct_payload
        raw_text = json.dumps(direct_payload, ensure_ascii=False)
    else:
        raw_text = extract_message_text(item)
        parsed = try_parse_json_text(raw_text)

    return custom_id, parsed, raw_text


def grouped_output_rows(parsed: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    if not isinstance(parsed, dict):
        return None
    rows = parsed.get("rows")
    if not isinstance(rows, list):
        return None
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized_rows.append(row)
    return normalized_rows


def main() -> None:
    args = parse_args()
    request_dir = args.request_root / args.queue_name
    request_manifest = load_json(request_dir / "manifest.json")
    request_index = load_tsv(request_dir / "request_index.tsv")
    request_by_id = {row["custom_id"]: row for row in request_index}
    request_rows_by_id: dict[str, list[dict[str, str]]] = {}
    request_rows_by_row_id: dict[str, dict[str, dict[str, str]]] = {}
    for row in request_index:
        request_custom_id = str(row.get("request_custom_id") or row.get("custom_id") or "")
        request_rows_by_id.setdefault(request_custom_id, []).append(row)
        row_id = str(row.get("row_id") or "")
        if row_id:
            request_rows_by_row_id.setdefault(request_custom_id, {})[row_id] = row

    response_files = sorted(args.response_dir.glob("*.jsonl"))
    if not response_files:
        raise SystemExit(f"no response jsonl files found in: {args.response_dir}")

    normalized_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []
    seen_row_keys: set[str] = set()

    for response_file in response_files:
        for item in iter_jsonl(response_file):
            custom_id, parsed, raw_text = normalize_response(item)
            if not custom_id:
                unresolved_rows.append(
                    {
                        "response_file": str(response_file),
                        "custom_id": "",
                        "error": "missing-custom-id",
                        "raw_text": raw_text,
                    }
                )
                continue
            request_meta = request_by_id.get(custom_id)
            request_meta_rows = request_rows_by_id.get(custom_id, [])
            if request_meta is None and not request_meta_rows:
                unresolved_rows.append(
                    {
                        "response_file": str(response_file),
                        "custom_id": custom_id,
                        "error": "custom-id-not-found",
                        "raw_text": raw_text,
                    }
                )
                continue
            if parsed is None:
                unresolved_rows.append(
                    {
                        "response_file": str(response_file),
                        "custom_id": custom_id,
                        "error": "unparseable-response-json",
                        "raw_text": raw_text,
                    }
                )
                continue

            grouped_rows = grouped_output_rows(parsed)
            if grouped_rows is not None and request_meta_rows:
                request_row_map = request_rows_by_row_id.get(custom_id, {})
                emitted_row_ids: set[str] = set()
                for grouped_row in grouped_rows:
                    row_id = str(grouped_row.get("id") or "")
                    request_row_meta = request_row_map.get(row_id)
                    if request_row_meta is None:
                        unresolved_rows.append(
                            {
                                "response_file": str(response_file),
                                "custom_id": custom_id,
                                "error": f"group-row-id-not-found:{row_id}",
                                "raw_text": raw_text,
                            }
                        )
                        continue
                    emitted_row_ids.add(row_id)
                    seen_row_keys.add(f"{custom_id}::{row_id}")
                    normalized_row = dict(request_row_meta)
                    normalized_row.update(
                        {
                            "response_file": str(response_file),
                            "request_custom_id": custom_id,
                            "custom_id": custom_id,
                            "decision": grouped_row.get("decision", ""),
                            "confidence": grouped_row.get("confidence", ""),
                            "suggested_chinese_text": grouped_row.get("suggested_chinese_text", ""),
                            "reason": grouped_row.get("reason", ""),
                            "raw_text": raw_text,
                        }
                    )
                    normalized_rows.append(normalized_row)
                for request_row_meta in request_meta_rows:
                    row_id = str(request_row_meta.get("row_id") or "")
                    if row_id and row_id not in emitted_row_ids:
                        unresolved_rows.append(
                            {
                                "response_file": str(response_file),
                                "custom_id": custom_id,
                                "error": f"group-row-missing:{row_id}",
                                "raw_text": raw_text,
                            }
                        )
                continue

            if request_meta is None:
                unresolved_rows.append(
                    {
                        "response_file": str(response_file),
                        "custom_id": custom_id,
                        "error": "request-meta-not-found",
                        "raw_text": raw_text,
                    }
                )
                continue

            row_id = str(request_meta.get("row_id") or "")
            if row_id:
                seen_row_keys.add(f"{custom_id}::{row_id}")
            else:
                seen_row_keys.add(custom_id)
            normalized_row = dict(request_meta)
            normalized_row.update(
                {
                    "response_file": str(response_file),
                    "request_custom_id": str(request_meta.get("request_custom_id") or custom_id),
                    "custom_id": custom_id,
                    "decision": parsed.get("decision", ""),
                    "confidence": parsed.get("confidence", ""),
                    "suggested_chinese_text": parsed.get("suggested_chinese_text", ""),
                    "reason": parsed.get("reason", ""),
                    "raw_text": raw_text,
                }
            )
            normalized_rows.append(normalized_row)

    missing_ids = []
    for row in request_index:
        row_id = str(row.get("row_id") or "")
        request_custom_id = str(row.get("request_custom_id") or row.get("custom_id") or "")
        row_key = f"{request_custom_id}::{row_id}" if row_id else request_custom_id
        if row_key not in seen_row_keys:
            missing_ids.append(row)
    decision_counts: dict[str, int] = {}
    for row in normalized_rows:
        decision = str(row.get("decision") or "")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    manifest = {
        "queue_name": args.queue_name,
        "request_root": str(args.request_root),
        "request_count": int(request_manifest.get("request_count") or 0),
        "response_file_count": len(response_files),
        "ingested_response_count": len(normalized_rows),
        "unresolved_response_count": len(unresolved_rows),
        "missing_response_count": len(missing_ids),
        "decision_counts": dict(sorted(decision_counts.items())),
        "response_files": [str(path) for path in response_files],
    }

    queue_output_dir = args.output_dir / args.queue_name
    write_json(queue_output_dir / "manifest.json", manifest)
    normalized_fieldnames = union_fieldnames(
        normalized_rows,
        [
            "response_file",
            "custom_id",
            "focus_rank",
            "part_name",
            "clip_name",
            "english_cue_id",
            "status",
            "match_origin",
            "source_clip_mismatch",
            "current_chinese_text",
            "decision",
            "confidence",
            "suggested_chinese_text",
            "reason",
            "raw_text",
        ],
    )
    write_tsv(
        queue_output_dir / "normalized_responses.tsv",
        normalized_rows,
        normalized_fieldnames,
    )
    write_jsonl(queue_output_dir / "normalized_responses.jsonl", normalized_rows)
    write_tsv(
        queue_output_dir / "unresolved_responses.tsv",
        unresolved_rows,
        ["response_file", "custom_id", "error", "raw_text"],
    )
    write_jsonl(queue_output_dir / "unresolved_responses.jsonl", unresolved_rows)
    missing_fieldnames = union_fieldnames(
        missing_ids,
        [
            "custom_id",
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
    write_tsv(
        queue_output_dir / "missing_requests.tsv",
        missing_ids,
        missing_fieldnames,
    )
    print(f"wrote ingested responses -> {queue_output_dir}")


if __name__ == "__main__":
    main()
