from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from build_phase_c_fulltrack_rebuild import part_short_name, write_srt


DEFAULT_PHASE_C_JSON = Path("scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2/all_segments.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_model_applied_v1")
DEFAULT_POINTER_PATH = Path("scratch/PHASE_C_CURRENT_MODEL_APPLIED.txt")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a Phase C model merge plan back onto all_segments.json.")
    parser.add_argument("--phase-c-json", type=Path, default=DEFAULT_PHASE_C_JSON)
    parser.add_argument("--merge-plan-tsv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--update-current-pointer", action="store_true")
    return parser.parse_args()


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


def write_pointer(path: Path, target_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(target_dir), encoding="utf-8")


def confidence_value(text: str) -> float | None:
    value = (text or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def apply_action(segment: dict[str, Any], action_row: dict[str, str]) -> tuple[bool, str]:
    action = str(action_row.get("action") or "").strip()
    decision = str(action_row.get("decision") or "").strip()
    queue_name = str(action_row.get("queue_name") or "").strip()
    suggested = str(action_row.get("replacement_text") or "").strip()
    confidence = confidence_value(str(action_row.get("confidence") or ""))
    reason = str(action_row.get("reason") or "").strip()

    if action == "keep-existing":
        segment["notes"] = f"{segment.get('notes') or ''} | model-keep:{queue_name}:{decision}".strip(" |")
        return False, "kept-existing"

    if action in {"clear-existing", "leave-unmatched"}:
        segment["status"] = "unmatched"
        segment["match_origin"] = "model-merge-plan-v1"
        segment["match_score"] = confidence
        segment["chinese_confidence"] = None
        segment["source_clip"] = None
        segment["chinese_text"] = ""
        segment["chinese_cue_ids"] = []
        segment["reviewed_source_segment_id"] = None
        segment["notes"] = f"model-clear:{queue_name}:{decision}:{reason}".strip(":")
        return True, action

    if action in {"replace-with-suggested-text", "fill-with-suggested-text"} and suggested:
        segment["status"] = "model-text-replace" if action == "replace-with-suggested-text" else "model-text-fill"
        segment["match_origin"] = "model-merge-plan-v1"
        segment["match_score"] = confidence
        segment["chinese_confidence"] = None
        segment["source_clip"] = None
        segment["chinese_text"] = suggested
        segment["chinese_cue_ids"] = []
        segment["reviewed_source_segment_id"] = None
        segment["notes"] = f"model-text:{queue_name}:{decision}:{reason}".strip(":")
        return True, action

    return False, "skipped-noop"


def build_summary(segments: list[dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    status_counts: Counter[str] = Counter()
    part_stats: dict[str, Counter[str]] = {}
    part_counts: dict[str, int] = {}
    for segment in segments:
        status = str(segment.get("status") or "unmatched")
        part_name = str(segment.get("part_name") or "")
        status_counts[status] += 1
        part_stats.setdefault(part_name, Counter())[status] += 1
        part_counts[part_name] = part_counts.get(part_name, 0) + 1

    parts = []
    for part_name in sorted(part_counts.keys()):
        counts = part_stats.get(part_name, Counter())
        matched_count = sum(count for status, count in counts.items() if status != "unmatched")
        parts.append(
            {
                "part_name": part_name,
                "segment_count": part_counts[part_name],
                "matched_count": matched_count,
                "coverage_ratio": round(matched_count / max(part_counts[part_name], 1), 4),
                "status_counts": dict(sorted(counts.items())),
            }
        )
    return dict(sorted(status_counts.items())), parts


def write_part_exports(output_dir: Path, segments: list[dict[str, Any]]) -> None:
    part_rows: dict[str, list[dict[str, Any]]] = {}
    for segment in segments:
        part_name = str(segment.get("part_name") or "")
        part_rows.setdefault(part_name, []).append(segment)

    for part_name, rows in sorted(part_rows.items()):
        short_name = part_short_name(part_name)
        part_dir = output_dir / short_name
        matched_count = sum(1 for row in rows if str(row.get("status") or "") != "unmatched")
        status_counts = Counter(str(row.get("status") or "unmatched") for row in rows)
        payload = {
            "part_name": part_name,
            "short_name": short_name,
            "segment_count": len(rows),
            "matched_count": matched_count,
            "coverage_ratio": round(matched_count / max(len(rows), 1), 4),
            "status_counts": dict(sorted(status_counts.items())),
            "segments": rows,
        }
        write_json(part_dir / f"{short_name}.draft.json", payload)
        write_tsv(part_dir / f"{short_name}.draft.tsv", rows, list(rows[0].keys()) if rows else [])
        write_srt(part_dir / f"{short_name}.draft.srt", rows)


def main() -> None:
    args = parse_args()
    phase_payload = json.loads(args.phase_c_json.read_text(encoding="utf-8"))
    manifest = dict(phase_payload["manifest"])
    segments = list(phase_payload["segments"])
    action_rows = load_tsv(args.merge_plan_tsv)

    segment_by_key = {
        (str(segment.get("part_name") or ""), str(segment.get("english_cue_id") or "")): segment
        for segment in segments
    }

    applied_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    action_counts: Counter[str] = Counter()

    for row in action_rows:
        key = (str(row.get("part_name") or ""), str(row.get("english_cue_id") or ""))
        segment = segment_by_key.get(key)
        if segment is None:
            skipped_rows.append({**row, "skip_reason": "segment-not-found"})
            continue

        changed, outcome = apply_action(segment, row)
        action_counts[outcome] += 1
        if changed:
            applied_rows.append({**row, "outcome": outcome})
        else:
            skipped_rows.append({**row, "skip_reason": outcome})

    status_counts, parts = build_summary(segments)
    matched_cues = sum(count for status, count in status_counts.items() if status != "unmatched")

    manifest["source_phase_c_json"] = str(args.phase_c_json)
    manifest["source_phase_c_version"] = str(phase_payload.get("manifest", {}).get("version") or "")
    manifest["version"] = args.output_dir.name or f"{manifest.get('version')}-model-applied-v1"
    manifest["matched_cues"] = matched_cues
    manifest["coverage_ratio"] = round(matched_cues / max(int(manifest.get("total_english_cues") or len(segments)), 1), 4)
    manifest["status_counts"] = status_counts
    manifest["parts"] = parts
    manifest["model_merge_plan_tsv"] = str(args.merge_plan_tsv)
    manifest["model_apply_action_counts"] = dict(sorted(action_counts.items()))
    manifest["model_apply_applied_count"] = len(applied_rows)
    manifest["model_apply_skipped_count"] = len(skipped_rows)

    output_payload = {
        "manifest": manifest,
        "segments": segments,
    }
    write_json(args.output_dir / "all_segments.json", output_payload)
    write_json(args.output_dir / "manifest.json", manifest)
    write_tsv(args.output_dir / "all_segments.tsv", segments, list(segments[0].keys()) if segments else [])
    write_part_exports(args.output_dir, segments)
    write_tsv(
        args.output_dir / "applied_actions.tsv",
        applied_rows,
        [
            "queue_name",
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
            "outcome",
        ],
    )
    write_tsv(
        args.output_dir / "skipped_actions.tsv",
        skipped_rows,
        [
            "queue_name",
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
            "skip_reason",
        ],
    )
    if args.update_current_pointer:
        write_pointer(DEFAULT_POINTER_PATH, args.output_dir)
    print(f"wrote applied phase c -> {args.output_dir}")


if __name__ == "__main__":
    main()
