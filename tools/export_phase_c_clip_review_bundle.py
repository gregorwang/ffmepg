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
    part_short_name,
    write_json,
)


DEFAULT_PHASE_C_JSON = Path("scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2/all_segments.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_clip_review_bundles_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export review bundles for specific low-coverage Phase C clips.")
    parser.add_argument("--mapping-json", type=Path, default=DEFAULT_MAPPING_JSON)
    parser.add_argument("--phase-c-json", type=Path, default=DEFAULT_PHASE_C_JSON)
    parser.add_argument("--english-ocr-root", type=Path, default=DEFAULT_ENGLISH_OCR_ROOT)
    parser.add_argument("--chinese-ocr-root", type=Path, default=DEFAULT_CHINESE_OCR_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--clips", nargs="+", required=True, help="One or more Chinese OCR clip folder names.")
    return parser.parse_args()


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_row_map(phase_c_rows: list[dict[str, Any]], part_name: str) -> dict[str, dict[str, Any]]:
    return {
        str(row["segment_id"]): row
        for row in phase_c_rows
        if str(row.get("part_name") or "") == part_name
    }


def summarize_unmatched_blocks(
    english_cues: list[FullEnglishCue],
    row_map: dict[str, dict[str, Any]],
    chinese_cues: list[FullChineseCue],
) -> list[dict[str, Any]]:
    if not english_cues:
        return []

    clip_start = float(english_cues[0].start)
    clip_end = float(english_cues[-1].end)
    clip_span = max(clip_end - clip_start, 1e-6)
    zh_count = len(chinese_cues)
    blocks: list[dict[str, Any]] = []
    current: list[FullEnglishCue] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        start_ratio = max(0.0, min(1.0, (current[0].start - clip_start) / clip_span))
        end_ratio = max(0.0, min(1.0, (current[-1].end - clip_start) / clip_span))
        zh_start = max(0, int(round(start_ratio * zh_count)) - 10)
        zh_end = min(zh_count, int(round(end_ratio * zh_count)) + 10)
        blocks.append(
            {
                "block_id": f"block_{len(blocks) + 1:03d}",
                "english_start_cue_id": current[0].cue_id,
                "english_end_cue_id": current[-1].cue_id,
                "english_count": len(current),
                "english_start_time": round(float(current[0].start), 3),
                "english_end_time": round(float(current[-1].end), 3),
                "english_preview": " ".join(cue.text for cue in current[:3]).strip(),
                "estimated_chinese_start_pos": zh_start,
                "estimated_chinese_end_pos": max(zh_start, zh_end - 1),
                "estimated_chinese_count": max(0, zh_end - zh_start),
                "estimated_chinese_preview": " ".join(cue.text for cue in chinese_cues[zh_start: min(zh_end, zh_start + 4)]).strip(),
            }
        )
        current = []

    for cue in english_cues:
        row = row_map.get(cue.cue_id)
        if row is not None and str(row.get("status") or "") != "unmatched":
            flush()
            continue
        current.append(cue)
    flush()
    return blocks


def export_clip_bundle(
    clip_name: str,
    mapping: dict[str, Any],
    phase_c_rows: list[dict[str, Any]],
    english_root: Path,
    chinese_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    clip_info = next((item for item in mapping.get("clips") or [] if str(item.get("clip_name") or "") == clip_name), None)
    if clip_info is None:
        raise SystemExit(f"clip not found in mapping: {clip_name}")

    part_name = str(clip_info["assigned_part"])
    english_cues = load_full_english_cues(english_root, part_name)
    clip_assignments = sorted(
        [item for item in mapping.get("clips") or [] if str(item.get("assigned_part") or "") == part_name],
        key=lambda item: int(item.get("clip_order_in_part") or 0),
    )
    english_by_clip = assign_clip_english_cues(english_cues, clip_assignments)
    clip_english = english_by_clip.get(clip_name, [])
    clip_chinese = load_full_chinese_cues(chinese_root, clip_name)
    row_map = build_row_map(phase_c_rows, part_name)

    chinese_used = {
        int(cue_id)
        for row in phase_c_rows
        if str(row.get("part_name") or "") == part_name
        and str(row.get("source_clip") or "") == clip_name
        and str(row.get("status") or "") != "unmatched"
        for cue_id in row.get("chinese_cue_ids") or []
        if str(cue_id).strip()
    }

    review_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    origin_counts: Counter[str] = Counter()
    for local_index, cue in enumerate(clip_english, start=1):
        row = row_map.get(cue.cue_id) or {}
        status = str(row.get("status") or "unmatched")
        origin = str(row.get("match_origin") or "none")
        status_counts[status] += 1
        origin_counts[origin] += 1
        review_rows.append(
            {
                "clip_name": clip_name,
                "part_name": part_name,
                "english_local_index": local_index,
                "english_cue_id": cue.cue_id,
                "start": cue.start,
                "end": cue.end,
                "status": status,
                "match_origin": origin,
                "match_score": row.get("match_score"),
                "source_clip": row.get("source_clip"),
                "english_text": cue.text,
                "chinese_cue_ids": ",".join(row.get("chinese_cue_ids") or []),
                "chinese_text": str(row.get("chinese_text") or ""),
                "notes": str(row.get("notes") or ""),
            }
        )

    chinese_rows = [
        {
            "clip_name": clip_name,
            "cue_index": cue.cue_index,
            "start": cue.start,
            "end": cue.end,
            "confidence": cue.confidence,
            "used_by_current_match": cue.cue_index in chinese_used,
            "text": cue.text,
        }
        for cue in clip_chinese
    ]

    unmatched_blocks = summarize_unmatched_blocks(clip_english, row_map, clip_chinese)
    clip_dir = output_dir / clip_name
    manifest = {
        "clip_name": clip_name,
        "part_name": part_name,
        "part_short_name": part_short_name(part_name),
        "english_count": len(clip_english),
        "chinese_count": len(clip_chinese),
        "matched_count": sum(1 for row in review_rows if row["status"] != "unmatched"),
        "coverage_ratio": round(
            sum(1 for row in review_rows if row["status"] != "unmatched") / max(len(review_rows), 1),
            4,
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "origin_counts": dict(sorted(origin_counts.items())),
        "unmatched_block_count": len(unmatched_blocks),
    }

    payload = {
        "manifest": manifest,
        "review_rows": review_rows,
        "chinese_cues": chinese_rows,
        "unmatched_blocks": unmatched_blocks,
    }
    write_json(clip_dir / "bundle.json", payload)
    write_json(clip_dir / "manifest.json", manifest)
    write_tsv(
        clip_dir / "review_rows.tsv",
        review_rows,
        [
            "clip_name",
            "part_name",
            "english_local_index",
            "english_cue_id",
            "start",
            "end",
            "status",
            "match_origin",
            "match_score",
            "source_clip",
            "english_text",
            "chinese_cue_ids",
            "chinese_text",
            "notes",
        ],
    )
    write_tsv(
        clip_dir / "chinese_cues.tsv",
        chinese_rows,
        [
            "clip_name",
            "cue_index",
            "start",
            "end",
            "confidence",
            "used_by_current_match",
            "text",
        ],
    )
    write_tsv(
        clip_dir / "unmatched_blocks.tsv",
        unmatched_blocks,
        [
            "block_id",
            "english_start_cue_id",
            "english_end_cue_id",
            "english_count",
            "english_start_time",
            "english_end_time",
            "english_preview",
            "estimated_chinese_start_pos",
            "estimated_chinese_end_pos",
            "estimated_chinese_count",
            "estimated_chinese_preview",
        ],
    )
    return manifest


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    phase_c_payload = json.loads(args.phase_c_json.read_text(encoding="utf-8"))
    phase_c_rows = list(phase_c_payload.get("segments") or [])

    clip_manifests = []
    for clip_name in args.clips:
        clip_manifests.append(
            export_clip_bundle(
                clip_name=clip_name,
                mapping=mapping,
                phase_c_rows=phase_c_rows,
                english_root=args.english_ocr_root,
                chinese_root=args.chinese_ocr_root,
                output_dir=args.output_dir,
            )
        )

    write_json(
        args.output_dir / "manifest.json",
        {
            "source_phase_c_json": str(args.phase_c_json),
            "clip_count": len(clip_manifests),
            "clips": clip_manifests,
        },
    )
    print(f"wrote review bundles -> {args.output_dir}")


if __name__ == "__main__":
    main()
