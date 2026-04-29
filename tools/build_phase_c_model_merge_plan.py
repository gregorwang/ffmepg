from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_INGEST_ROOT = Path("scratch/phase_c_model_response_ingest_v1")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_model_merge_plan_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a merge plan from ingested Phase C model responses.")
    parser.add_argument("--ingest-root", type=Path, default=DEFAULT_INGEST_ROOT)
    parser.add_argument("--queue-names", nargs="+", required=True)
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


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def normalize_decision(decision: str) -> str:
    return (decision or "").strip().lower()


def plan_action(row: dict[str, str]) -> tuple[str, str]:
    decision = normalize_decision(str(row.get("decision") or ""))
    suggested_text = str(row.get("suggested_chinese_text") or "").strip()
    current_text = str(row.get("current_chinese_text") or "").strip()

    if decision == "keep_current_match":
        return "keep-existing", ""
    if decision == "reject_current_match":
        if current_text:
            return "clear-existing", ""
        return "leave-unmatched", ""
    if decision == "suggest_new_match":
        if suggested_text:
            if current_text:
                return "replace-with-suggested-text", suggested_text
            return "fill-with-suggested-text", suggested_text
        return "manual-review", ""
    if decision == "no_match":
        if current_text:
            return "clear-existing", ""
        return "leave-unmatched", ""
    if decision == "unsure":
        return "manual-review", ""
    return "unrecognized-decision", ""


def confidence_value(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def queue_priority(queue_name: str) -> tuple[int, int]:
    normalized = (queue_name or "").strip().lower()
    retry_match = re.fullmatch(r"retry_round(\d+)", normalized)
    if retry_match:
        return (100, int(retry_match.group(1)))

    base_order = {
        "first_pass_match_fix": (10, 1),
        "remaining_match_fix": (10, 2),
        "unmatched_rich": (10, 3),
        "unmatched_rest": (10, 4),
    }
    return base_order.get(normalized, (1, 0))


def row_target_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("part_name") or ""), str(row.get("english_cue_id") or "")


def row_sort_key(row: dict[str, Any]) -> tuple[int, int, float, str]:
    priority_major, priority_minor = queue_priority(str(row.get("queue_name") or ""))
    confidence = confidence_value(str(row.get("confidence") or "")) or -1.0
    custom_id = str(row.get("custom_id") or "")
    return priority_major, priority_minor, confidence, custom_id


def main() -> None:
    args = parse_args()
    action_rows_all: list[dict[str, Any]] = []
    queue_manifests: list[dict[str, Any]] = []
    source_action_counts: Counter[str] = Counter()
    source_decision_counts: Counter[str] = Counter()
    source_part_counts: Counter[str] = Counter()

    for queue_name in args.queue_names:
        queue_dir = args.ingest_root / queue_name
        manifest_path = queue_dir / "manifest.json"
        normalized_path = queue_dir / "normalized_responses.tsv"
        unresolved_path = queue_dir / "unresolved_responses.tsv"
        missing_path = queue_dir / "missing_requests.tsv"

        manifest = load_json(manifest_path)
        normalized_rows = load_tsv(normalized_path)
        unresolved_rows = load_tsv(unresolved_path) if unresolved_path.exists() else []
        missing_rows = load_tsv(missing_path) if missing_path.exists() else []

        queue_manifests.append(
            {
                "queue_name": queue_name,
                "ingested_response_count": int(manifest.get("ingested_response_count") or 0),
                "unresolved_response_count": int(manifest.get("unresolved_response_count") or 0),
                "missing_response_count": int(manifest.get("missing_response_count") or 0),
                "unresolved_rows": len(unresolved_rows),
                "missing_rows": len(missing_rows),
            }
        )

        for row in normalized_rows:
            decision = normalize_decision(str(row.get("decision") or ""))
            action, replacement_text = plan_action(row)
            confidence = confidence_value(str(row.get("confidence") or ""))

            part_name = str(row.get("part_name") or "")
            source_part_counts[part_name] += 1
            source_decision_counts[decision] += 1
            source_action_counts[action] += 1

            action_rows_all.append(
                {
                    "queue_name": queue_name,
                    "source_queue_name": str(row.get("source_queue_name") or queue_name),
                    "original_custom_id": str(row.get("original_custom_id") or ""),
                    "retry_reason": str(row.get("retry_reason") or ""),
                    "part_name": part_name,
                    "clip_name": str(row.get("clip_name") or ""),
                    "english_cue_id": str(row.get("english_cue_id") or ""),
                    "custom_id": str(row.get("custom_id") or ""),
                    "status": str(row.get("status") or ""),
                    "match_origin": str(row.get("match_origin") or ""),
                    "source_clip_mismatch": str(row.get("source_clip_mismatch") or ""),
                    "decision": decision,
                    "confidence": confidence if confidence is not None else "",
                    "action": action,
                    "current_chinese_text": str(row.get("current_chinese_text") or ""),
                    "suggested_chinese_text": str(row.get("suggested_chinese_text") or ""),
                    "replacement_text": replacement_text,
                    "reason": str(row.get("reason") or ""),
                }
            )

    deduped_rows_by_target: dict[tuple[str, str], dict[str, Any]] = {}
    superseded_rows: list[dict[str, Any]] = []
    for row in sorted(action_rows_all, key=row_sort_key):
        target_key = row_target_key(row)
        previous = deduped_rows_by_target.get(target_key)
        if previous is not None:
            superseded_rows.append(
                {
                    "part_name": row["part_name"],
                    "english_cue_id": row["english_cue_id"],
                    "kept_queue_name": row["queue_name"],
                    "replaced_queue_name": previous["queue_name"],
                    "kept_custom_id": row["custom_id"],
                    "replaced_custom_id": previous["custom_id"],
                }
            )
        deduped_rows_by_target[target_key] = row

    action_rows = list(deduped_rows_by_target.values())
    action_rows.sort(
        key=lambda row: (
            row["part_name"],
            row["clip_name"],
            row["english_cue_id"],
            row["queue_name"],
        )
    )

    decision_counts: Counter[str] = Counter(str(row.get("decision") or "") for row in action_rows)
    action_counts: Counter[str] = Counter(str(row.get("action") or "") for row in action_rows)
    part_counts: Counter[str] = Counter(str(row.get("part_name") or "") for row in action_rows)

    summary = {
        "queue_count": len(queue_manifests),
        "source_row_count": len(action_rows_all),
        "row_count": len(action_rows),
        "superseded_row_count": len(superseded_rows),
        "source_decision_counts": dict(sorted(source_decision_counts.items())),
        "decision_counts": dict(sorted(decision_counts.items())),
        "source_action_counts": dict(sorted(source_action_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "source_part_counts": dict(sorted(source_part_counts.items())),
        "part_counts": dict(sorted(part_counts.items())),
        "queues": queue_manifests,
    }

    write_json(args.output_dir / "manifest.json", summary)
    write_json(args.output_dir / "merge_plan.json", {"manifest": summary, "rows": action_rows, "superseded_rows": superseded_rows})
    write_tsv(
        args.output_dir / "actions.tsv",
        action_rows,
        [
            "queue_name",
            "source_queue_name",
            "original_custom_id",
            "retry_reason",
            "part_name",
            "clip_name",
            "english_cue_id",
            "custom_id",
            "status",
            "match_origin",
            "source_clip_mismatch",
            "decision",
            "confidence",
            "action",
            "current_chinese_text",
            "suggested_chinese_text",
            "replacement_text",
            "reason",
        ],
    )
    write_tsv(
        args.output_dir / "superseded_rows.tsv",
        superseded_rows,
        [
            "part_name",
            "english_cue_id",
            "kept_queue_name",
            "replaced_queue_name",
            "kept_custom_id",
            "replaced_custom_id",
        ],
    )
    print(f"wrote merge plan -> {args.output_dir}")


if __name__ == "__main__":
    main()
