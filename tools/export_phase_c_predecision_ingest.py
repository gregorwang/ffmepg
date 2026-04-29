from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_SPEAKERTRIM_DIR = Path("scratch/phase_c_llm_screening_pack_v6_speakertrim")
DEFAULT_SHORTTRIM_DIR = Path("scratch/phase_c_llm_screening_pack_v14_shorttrim120")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_predecision_ingest_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export deterministic Phase C screening predecisions into ingest-root format."
    )
    parser.add_argument("--speakertrim-dir", type=Path, default=DEFAULT_SPEAKERTRIM_DIR)
    parser.add_argument("--shorttrim-dir", type=Path, default=DEFAULT_SHORTTRIM_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--speaker-queue-name", type=str, default="auto_speaker_rules")
    parser.add_argument("--shorttrim-queue-name", type=str, default="auto_shorttrim_no_match")
    parser.add_argument("--coarse-auto-decisions-tsv", type=Path)
    parser.add_argument("--coarse-queue-name", type=str, default="auto_coarse_matchfix_keep")
    parser.add_argument("--extra-no-match-tsv", type=Path)
    parser.add_argument("--extra-no-match-queue-name", type=str, default="auto_final_unmatched_no_match")
    parser.add_argument("--confidence", type=float, default=1.0)
    return parser.parse_args()


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


def speaker_rows(rows: list[dict[str, str]], queue_name: str, confidence: float) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        custom_id = f"{queue_name}:{index:05d}"
        raw_payload = {
            "decision": row.get("auto_decision", ""),
            "confidence": confidence,
            "reason": row.get("auto_reason", ""),
        }
        normalized.append(
            {
                "response_file": "",
                "request_custom_id": custom_id,
                "custom_id": custom_id,
                "source_queue_name": str(row.get("queue_name") or ""),
                "focus_rank": str(row.get("focus_rank") or ""),
                "part_name": str(row.get("part_name") or ""),
                "clip_name": str(row.get("clip_name") or ""),
                "english_cue_id": str(row.get("english_cue_id") or ""),
                "status": str(row.get("status") or ""),
                "match_origin": str(row.get("match_origin") or ""),
                "source_clip_mismatch": str(row.get("source_clip_mismatch") or ""),
                "current_chinese_text": str(row.get("current_chinese_text") or ""),
                "decision": str(row.get("auto_decision") or ""),
                "confidence": confidence,
                "suggested_chinese_text": "",
                "reason": str(row.get("auto_reason") or ""),
                "raw_text": json.dumps(raw_payload, ensure_ascii=False),
            }
        )
    return normalized


def shorttrim_rows(rows: list[dict[str, str]], queue_name: str, confidence: float) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        custom_id = f"{queue_name}:{index:05d}"
        raw_payload = {
            "decision": "no_match",
            "confidence": confidence,
            "reason": row.get("drop_reason", ""),
        }
        normalized.append(
            {
                "response_file": "",
                "request_custom_id": custom_id,
                "custom_id": custom_id,
                "source_queue_name": str(row.get("queue_name") or ""),
                "focus_rank": str(row.get("focus_rank") or ""),
                "part_name": str(row.get("part_name") or ""),
                "clip_name": str(row.get("clip_name") or ""),
                "english_cue_id": str(row.get("english_cue_id") or ""),
                "status": "unmatched",
                "match_origin": "",
                "source_clip_mismatch": "",
                "current_chinese_text": "",
                "decision": "no_match",
                "confidence": confidence,
                "suggested_chinese_text": "",
                "reason": str(row.get("drop_reason") or ""),
                "raw_text": json.dumps(raw_payload, ensure_ascii=False),
            }
        )
    return normalized


def write_queue(output_dir: Path, queue_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    queue_dir = output_dir / queue_name
    decision_counts: dict[str, int] = {}
    for row in rows:
        decision = str(row.get("decision") or "")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    manifest = {
        "queue_name": queue_name,
        "request_root": "predecision-ingest",
        "request_count": len(rows),
        "response_file_count": 0,
        "ingested_response_count": len(rows),
        "unresolved_response_count": 0,
        "missing_response_count": 0,
        "decision_counts": dict(sorted(decision_counts.items())),
        "response_files": [],
    }
    fieldnames = [
        "response_file",
        "request_custom_id",
        "custom_id",
        "source_queue_name",
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
    ]
    write_json(queue_dir / "manifest.json", manifest)
    write_tsv(queue_dir / "normalized_responses.tsv", rows, fieldnames)
    write_jsonl(queue_dir / "normalized_responses.jsonl", rows)
    write_tsv(queue_dir / "unresolved_responses.tsv", [], ["response_file", "custom_id", "error", "raw_text"])
    write_jsonl(queue_dir / "unresolved_responses.jsonl", [])
    write_tsv(
        queue_dir / "missing_requests.tsv",
        [],
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
    return manifest


def main() -> None:
    args = parse_args()
    speaker_source_rows = load_tsv(args.speakertrim_dir / "auto_decisions.tsv")
    shorttrim_source_rows = load_tsv(args.shorttrim_dir / "dropped_rows.tsv")

    speaker_normalized = speaker_rows(speaker_source_rows, args.speaker_queue_name, args.confidence)
    shorttrim_normalized = shorttrim_rows(shorttrim_source_rows, args.shorttrim_queue_name, args.confidence)
    coarse_source_rows = load_tsv(args.coarse_auto_decisions_tsv) if args.coarse_auto_decisions_tsv else []
    coarse_normalized = speaker_rows(coarse_source_rows, args.coarse_queue_name, args.confidence)
    extra_no_match_source_rows = load_tsv(args.extra_no_match_tsv) if args.extra_no_match_tsv else []
    extra_no_match_normalized = shorttrim_rows(extra_no_match_source_rows, args.extra_no_match_queue_name, args.confidence)

    speaker_manifest = write_queue(args.output_dir, args.speaker_queue_name, speaker_normalized)
    shorttrim_manifest = write_queue(args.output_dir, args.shorttrim_queue_name, shorttrim_normalized)
    queue_manifests = [speaker_manifest, shorttrim_manifest]
    coarse_manifest: dict[str, Any] | None = None
    if coarse_normalized:
        coarse_manifest = write_queue(args.output_dir, args.coarse_queue_name, coarse_normalized)
        queue_manifests.append(coarse_manifest)
    extra_no_match_manifest: dict[str, Any] | None = None
    if extra_no_match_normalized:
        extra_no_match_manifest = write_queue(args.output_dir, args.extra_no_match_queue_name, extra_no_match_normalized)
        queue_manifests.append(extra_no_match_manifest)

    root_manifest = {
        "speakertrim_dir": str(args.speakertrim_dir),
        "shorttrim_dir": str(args.shorttrim_dir),
        "speaker_queue_name": args.speaker_queue_name,
        "shorttrim_queue_name": args.shorttrim_queue_name,
        "coarse_auto_decisions_tsv": str(args.coarse_auto_decisions_tsv) if args.coarse_auto_decisions_tsv else "",
        "coarse_queue_name": args.coarse_queue_name if coarse_normalized else "",
        "extra_no_match_tsv": str(args.extra_no_match_tsv) if args.extra_no_match_tsv else "",
        "extra_no_match_queue_name": args.extra_no_match_queue_name if extra_no_match_normalized else "",
        "total_ingested_rows": len(speaker_normalized) + len(shorttrim_normalized) + len(coarse_normalized) + len(extra_no_match_normalized),
        "queue_manifests": queue_manifests,
    }
    write_json(args.output_dir / "manifest.json", root_manifest)
    queue_summary_rows = [
        {
            "queue_name": args.speaker_queue_name,
            "row_count": len(speaker_normalized),
            "decision_counts": json.dumps(speaker_manifest["decision_counts"], ensure_ascii=False),
        },
        {
            "queue_name": args.shorttrim_queue_name,
            "row_count": len(shorttrim_normalized),
            "decision_counts": json.dumps(shorttrim_manifest["decision_counts"], ensure_ascii=False),
        },
    ]
    if coarse_normalized:
        queue_summary_rows.append(
            {
                "queue_name": args.coarse_queue_name,
                "row_count": len(coarse_normalized),
                "decision_counts": json.dumps((coarse_manifest or {}).get("decision_counts", {}), ensure_ascii=False),
            }
        )
    if extra_no_match_normalized:
        queue_summary_rows.append(
            {
                "queue_name": args.extra_no_match_queue_name,
                "row_count": len(extra_no_match_normalized),
                "decision_counts": json.dumps((extra_no_match_manifest or {}).get("decision_counts", {}), ensure_ascii=False),
            }
        )
    write_tsv(args.output_dir / "queue_summary.tsv", queue_summary_rows, ["queue_name", "row_count", "decision_counts"])
    print(f"wrote predecision ingest root -> {args.output_dir}")


if __name__ == "__main__":
    main()
