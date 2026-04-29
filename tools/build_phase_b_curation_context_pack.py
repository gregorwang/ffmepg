from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a context-rich review pack from a Phase B curation pack."
    )
    parser.add_argument("--curation-dir", type=Path, required=True)
    parser.add_argument("--master-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--context-radius", type=int, default=1)
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "curation_id",
        "priority",
        "review_action",
        "part_name",
        "source_clip",
        "start",
        "end",
        "match_score",
        "selection_mode",
        "reason_tags",
        "english_text",
        "chinese_text",
        "prev_context",
        "next_context",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            narrowed = {
                "curation_id": row["curation_id"],
                "priority": row["priority"],
                "review_action": row["review_action"],
                "part_name": row["part_name"],
                "source_clip": row["source_clip"],
                "start": row["start"],
                "end": row["end"],
                "match_score": row["match_score"],
                "selection_mode": row["selection_mode"],
                "reason_tags": ",".join(row["reason_tags"]),
                "english_text": row["english_text"],
                "chinese_text": row["chinese_text"],
                "prev_context": " || ".join(row["prev_context"]),
                "next_context": " || ".join(row["next_context"]),
            }
            writer.writerow(
                narrowed
            )


def recommend_action(row: dict[str, Any]) -> str:
    selection_mode = str(row["selection_mode"])
    reason_tags = set(row["reason_tags"])
    if selection_mode in {"manual-replacement", "manual-accepted-compression"}:
        return "check_compression_or_omission"
    if selection_mode in {"manual-override", "manual-text-cleanup"}:
        return "check_wording_and_merge"
    if selection_mode == "anchor-fallback":
        return "confirm_anchor_alignment"
    if "partial-segment" in reason_tags:
        return "confirm_partial_alignment"
    if "accepted-low-score" in reason_tags:
        return "spot_check_low_score"
    return "general_review"


def compact_segment(seg: dict[str, Any]) -> str:
    return f"{seg['start']:.1f}-{seg['end']:.1f} | {seg['english_text']} => {seg['chinese_text']}"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Phase B Curation Context Pack",
        "",
        f"- Source curation pack: `{payload['source_curation_version']}`",
        f"- Items: `{payload['item_count']}`",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"## {item['curation_id']} {item['part_name']}",
                "",
                f"- Priority: `{item['priority']}`",
                f"- Review action: `{item['review_action']}`",
                f"- Selection mode: `{item['selection_mode']}`",
                f"- Match score: `{item['match_score']}`",
                f"- Source clip: `{item['source_clip']}`",
                f"- Reason tags: `{', '.join(item['reason_tags'])}`",
                "",
                f"- English: {item['english_text']}",
                f"- Chinese: {item['chinese_text']}",
                "",
                "Prev context:",
            ]
        )
        if item["prev_context"]:
            lines.extend([f"- {entry}" for entry in item["prev_context"]])
        else:
            lines.append("- None")
        lines.append("")
        lines.append("Next context:")
        if item["next_context"]:
            lines.extend([f"- {entry}" for entry in item["next_context"]])
        else:
            lines.append("- None")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    curation_payload = json.loads((args.curation_dir / "curation_segments.json").read_text(encoding="utf-8"))
    master_payload = json.loads((args.master_dir / "all_segments.json").read_text(encoding="utf-8"))

    curated = [row for row in curation_payload["segments"] if row["priority"] == "high"]
    master_segments = list(master_payload["segments"])
    by_part: dict[str, list[dict[str, Any]]] = {}
    for seg in master_segments:
        by_part.setdefault(seg["part_name"], []).append(seg)
    for segs in by_part.values():
        segs.sort(key=lambda item: (item["start"], item["end"], item["global_segment_id"]))

    items: list[dict[str, Any]] = []
    for row in curated:
        part_segments = by_part[row["part_name"]]
        index = next(i for i, seg in enumerate(part_segments) if seg["global_segment_id"] == row["global_segment_id"])
        prev_segments = part_segments[max(0, index - args.context_radius):index]
        next_segments = part_segments[index + 1:index + 1 + args.context_radius]
        item = {
            **row,
            "review_action": recommend_action(row),
            "prev_context": [compact_segment(seg) for seg in prev_segments],
            "next_context": [compact_segment(seg) for seg in next_segments],
        }
        items.append(item)

    payload = {
        "version": "phase-b-curation-context-pack-v1",
        "source_curation_dir": str(args.curation_dir),
        "source_curation_version": curation_payload["manifest"]["version"],
        "source_master_dir": str(args.master_dir),
        "item_count": len(items),
        "items": items,
    }

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "context_items.json", payload)
    write_tsv(output_dir / "context_items.tsv", items)
    (output_dir / "README.md").write_text(build_markdown(payload), encoding="utf-8")
    print(f"wrote context pack -> {output_dir}")


if __name__ == "__main__":
    main()
