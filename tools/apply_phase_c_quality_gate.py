from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from build_phase_c_fulltrack_rebuild import part_short_name, write_json, write_srt, write_tsv
from phase_b_sequence_align import normalize_text, prepare_chinese_text, prepare_english_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply conservative quality gates to a Phase C draft output.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version-label", type=str, default="phase_c_quality_gate_qc1")
    return parser.parse_args()


def english_word_count(text: str) -> int:
    return len([part for part in re.split(r"\s+", text.strip()) if part])


def cjk_count(text: str) -> int:
    return sum("\u4e00" <= ch <= "\u9fff" for ch in text)


def ascii_alpha_count(text: str) -> int:
    return sum(ch.isascii() and ch.isalpha() for ch in text)


def has_explicit_speaker(text: str) -> bool:
    normalized = normalize_text(text)
    if "：" in normalized:
        prefix = normalized.split("：", 1)[0].strip()
        return 0 < len(prefix) <= 12
    if ":" in normalized:
        prefix = normalized.split(":", 1)[0].strip()
        return 0 < len(prefix) <= 30 and prefix[:1].isalpha()
    return False


def repeated_phrase(text: str) -> bool:
    normalized = re.sub(r"\s+", "", normalize_text(text))
    return bool(normalized and re.search(r"(.{2,})\1\1", normalized))


def evaluate_row(row: dict[str, Any]) -> tuple[bool, list[str]]:
    if row.get("match_origin") in {"none", "reviewed-master"}:
        return False, []

    english_text = str(row.get("english_text") or "")
    chinese_text = str(row.get("chinese_text") or "")
    english_semantic = prepare_english_text(english_text)
    chinese_semantic = prepare_chinese_text(chinese_text)
    english_words = english_word_count(english_semantic or english_text)
    zh_cjk = cjk_count(chinese_text)
    zh_ascii = ascii_alpha_count(chinese_text)
    english_has_speaker = has_explicit_speaker(english_text)
    chinese_has_speaker = has_explicit_speaker(chinese_text)
    match_origin = str(row.get("match_origin") or "")
    score = float(row.get("match_score") or 0.0)

    reasons: list[str] = []
    if zh_cjk == 0:
        reasons.append("no-cjk")
    if zh_ascii >= 3:
        reasons.append("ascii-noise")
    if repeated_phrase(chinese_text):
        reasons.append("repeated-ocr-fragment")
    if not chinese_semantic and english_words >= 2:
        reasons.append("empty-semantic-after-clean")
    if zh_cjk <= 2 and english_words >= 2:
        reasons.append("too-short-for-english-length")
    if english_has_speaker and not chinese_has_speaker and zh_cjk <= 4 and english_words >= 2:
        reasons.append("speaker-missing-on-short-zh")
    if match_origin == "group-anchor-window-v1" and zh_cjk <= 4 and english_words >= 2 and score < 0.75:
        reasons.append("short-group-match")

    return bool(reasons), reasons


def sanitize_row(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    updated = dict(row)
    updated["status"] = "unmatched"
    updated["match_origin"] = "quality-gated-qc1"
    updated["match_score"] = None
    updated["chinese_confidence"] = None
    updated["source_clip"] = None
    updated["chinese_text"] = ""
    updated["chinese_cue_ids"] = []
    updated["notes"] = f"qc1-rejected: {', '.join(reasons)}"
    return updated


def write_audit_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "part_name",
        "segment_id",
        "old_status",
        "old_match_origin",
        "old_match_score",
        "reasons",
        "english_text",
        "chinese_text",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    args = parse_args()
    all_segments_path = args.input_dir / "all_segments.json"
    payload = json.loads(all_segments_path.read_text(encoding="utf-8"))
    source_manifest = dict(payload.get("manifest") or {})
    source_rows = list(payload.get("segments") or [])

    filtered_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    rejected_by_reason: Counter[str] = Counter()
    rejected_by_origin: Counter[str] = Counter()

    for row in source_rows:
        reject, reasons = evaluate_row(row)
        if reject:
            for reason in reasons:
                rejected_by_reason[reason] += 1
            rejected_by_origin[str(row.get("match_origin") or "")] += 1
            audit_rows.append(
                {
                    "part_name": row["part_name"],
                    "segment_id": row["segment_id"],
                    "old_status": row["status"],
                    "old_match_origin": row["match_origin"],
                    "old_match_score": row["match_score"],
                    "reasons": ",".join(reasons),
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                }
            )
            filtered_rows.append(sanitize_row(row, reasons))
        else:
            filtered_rows.append(dict(row))

    filtered_rows.sort(key=lambda item: (item["part_name"], float(item["start"]), float(item["end"]), item["segment_id"]))
    part_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in filtered_rows:
        part_groups[str(row["part_name"])].append(row)

    total_status_counts = Counter(str(row["status"]) for row in filtered_rows)
    matched_cues = sum(1 for row in filtered_rows if str(row["status"]) != "unmatched")
    manifest = {
        "version": args.version_label,
        "source_output_dir": str(args.input_dir),
        "source_mapping_json": source_manifest.get("mapping_json"),
        "source_reviewed_master_json": source_manifest.get("reviewed_master_json"),
        "total_english_cues": len(filtered_rows),
        "matched_cues": matched_cues,
        "coverage_ratio": round(matched_cues / max(len(filtered_rows), 1), 4),
        "status_counts": dict(sorted(total_status_counts.items())),
        "rejected_row_count": len(audit_rows),
        "rejected_by_reason": dict(sorted(rejected_by_reason.items())),
        "rejected_by_origin": dict(sorted(rejected_by_origin.items())),
        "parts": [],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "all_segments.json", {"manifest": manifest, "segments": filtered_rows})
    write_tsv(args.output_dir / "all_segments.tsv", filtered_rows)
    write_audit_tsv(args.output_dir / "qc1_rejected_rows.tsv", audit_rows)
    write_json(args.output_dir / "qc1_rejected_rows.json", {"rows": audit_rows})

    for part_name, rows in sorted(part_groups.items()):
        matched_count = sum(1 for row in rows if str(row["status"]) != "unmatched")
        status_counts = Counter(str(row["status"]) for row in rows)
        short_name = part_short_name(part_name)
        part_payload = {
            "part_name": part_name,
            "short_name": short_name,
            "segment_count": len(rows),
            "matched_count": matched_count,
            "coverage_ratio": round(matched_count / max(len(rows), 1), 4),
            "status_counts": dict(sorted(status_counts.items())),
            "segments": rows,
        }
        manifest["parts"].append(
            {
                "part_name": part_name,
                "segment_count": len(rows),
                "matched_count": matched_count,
                "coverage_ratio": round(matched_count / max(len(rows), 1), 4),
                "status_counts": dict(sorted(status_counts.items())),
            }
        )
        write_json(args.output_dir / short_name / f"{short_name}.draft.json", part_payload)
        write_tsv(args.output_dir / short_name / f"{short_name}.draft.tsv", rows)
        write_srt(args.output_dir / short_name / f"{short_name}.draft.srt", rows)

    write_json(args.output_dir / "manifest.json", manifest)
    print(f"wrote qc output -> {args.output_dir}")
    print(f"rejected rows -> {len(audit_rows)}")


if __name__ == "__main__":
    main()
