from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_model_handoff_v1")
DEFAULT_HANDOFF_POINTER = Path("scratch/PHASE_C_CURRENT_MODEL_HANDOFF.txt")
DEFAULT_REQUEST_POINTER = Path("scratch/PHASE_C_CURRENT_MODEL_REQUESTS.txt")
DEFAULT_RETRY_POINTER = Path("scratch/PHASE_C_CURRENT_MODEL_RETRY_REQUESTS.txt")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Phase C model handoff summary for the current round and next round.")
    parser.add_argument("--request-root", type=Path, required=True)
    parser.add_argument("--queue-names", nargs="+", required=True)
    parser.add_argument("--ingest-root", type=Path, required=True)
    parser.add_argument("--merge-plan-dir", type=Path, required=True)
    parser.add_argument("--applied-output-dir", type=Path, required=True)
    parser.add_argument("--delta-output-dir", type=Path, required=True)
    parser.add_argument("--burnin-output-dir", type=Path, required=True)
    parser.add_argument("--next-retry-output-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--update-current-pointers", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def retry_round_number(queue_name: str) -> int | None:
    match = re.fullmatch(r"retry_round(\d+)", (queue_name or "").strip().lower())
    return int(match.group(1)) if match else None


def queue_sort_key(queue_name: str) -> tuple[int, int, str]:
    retry_number = retry_round_number(queue_name)
    if retry_number is not None:
        return (100, retry_number, queue_name)
    base_order = {
        "first_pass_match_fix": (10, 1, queue_name),
        "remaining_match_fix": (10, 2, queue_name),
        "unmatched_rich": (10, 3, queue_name),
        "unmatched_rest": (10, 4, queue_name),
    }
    return base_order.get(queue_name, (1, 0, queue_name))


def detect_next_retry_queue(next_retry_output_dir: Path | None) -> tuple[str | None, dict[str, Any] | None]:
    if next_retry_output_dir is None or not next_retry_output_dir.exists():
        return None, None
    queue_dirs = [path for path in next_retry_output_dir.iterdir() if path.is_dir() and (path / "manifest.json").exists()]
    if not queue_dirs:
        return None, None
    queue_dirs.sort(key=lambda path: queue_sort_key(path.name))
    queue_dir = queue_dirs[-1]
    return queue_dir.name, load_json(queue_dir / "manifest.json")


def pointer_root_text(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def main() -> None:
    args = parse_args()
    current_queue_entries: list[dict[str, Any]] = []
    for queue_name in args.queue_names:
        request_manifest = load_json(args.request_root / queue_name / "manifest.json")
        ingest_manifest = load_json(args.ingest_root / queue_name / "manifest.json")
        current_queue_entries.append(
            {
                "queue_name": queue_name,
                "request_count": int(request_manifest.get("request_count") or 0),
                "batch_count": int(request_manifest.get("batch_count") or 0),
                "ingested_response_count": int(ingest_manifest.get("ingested_response_count") or 0),
                "unresolved_response_count": int(ingest_manifest.get("unresolved_response_count") or 0),
                "missing_response_count": int(ingest_manifest.get("missing_response_count") or 0),
                "decision_counts": dict(ingest_manifest.get("decision_counts") or {}),
            }
        )

    merge_manifest = load_json(args.merge_plan_dir / "manifest.json")
    applied_manifest = load_json(args.applied_output_dir / "manifest.json")
    delta_manifest = load_json(args.delta_output_dir / "manifest.json")
    burnin_manifest = load_json(args.burnin_output_dir / "manifest.json")

    next_queue_name, next_queue_manifest = detect_next_retry_queue(args.next_retry_output_dir)
    next_round: dict[str, Any] | None = None
    next_action = "complete"
    if next_queue_name and next_queue_manifest:
        next_request_count = int(next_queue_manifest.get("request_count") or 0)
        next_round = {
            "request_root": str(args.next_retry_output_dir),
            "queue_name": next_queue_name,
            "request_count": next_request_count,
            "batch_count": int(next_queue_manifest.get("batch_count") or 0),
            "retry_reason_counts": dict(next_queue_manifest.get("retry_reason_counts") or {}),
            "source_queues": list(next_queue_manifest.get("source_queues") or []),
        }
        next_action = "run_model" if next_request_count > 0 else "complete"

    handoff = {
        "current_round": {
            "request_root": str(args.request_root),
            "queue_names": list(args.queue_names),
            "queues": current_queue_entries,
            "merge_plan": merge_manifest,
            "applied": {
                "output_dir": str(args.applied_output_dir),
                "version": applied_manifest.get("version"),
                "matched_cues": applied_manifest.get("matched_cues"),
                "coverage_ratio": applied_manifest.get("coverage_ratio"),
                "model_apply_action_counts": dict(applied_manifest.get("model_apply_action_counts") or {}),
            },
            "delta": {
                "output_dir": str(args.delta_output_dir),
                "changed_row_count": delta_manifest.get("changed_row_count"),
                "change_type_counts": dict(delta_manifest.get("change_type_counts") or {}),
            },
            "burnin": {
                "output_dir": str(args.burnin_output_dir),
                "part_count": burnin_manifest.get("part_count"),
            },
        },
        "next_round": next_round,
        "next_action": next_action,
    }

    write_json(args.output_dir / "handoff.json", handoff)
    write_json(args.output_dir / "manifest.json", {
        "current_queue_count": len(args.queue_names),
        "next_action": next_action,
        "has_next_round": next_round is not None,
    })
    if args.update_current_pointers:
        write_text(DEFAULT_HANDOFF_POINTER, pointer_root_text(args.output_dir))

        if next_round and int(next_round.get("request_count") or 0) > 0:
            request_pointer_text = f"{pointer_root_text(args.next_retry_output_dir)}\n{next_queue_name}\n"
            write_text(DEFAULT_REQUEST_POINTER, request_pointer_text)
            if next_queue_name and retry_round_number(next_queue_name) is not None:
                write_text(DEFAULT_RETRY_POINTER, pointer_root_text(args.next_retry_output_dir / next_queue_name))

    print(f"wrote phase c model handoff -> {args.output_dir}")


if __name__ == "__main__":
    main()
