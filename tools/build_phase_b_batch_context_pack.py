from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a context-rich review pack from a Phase B medium review batch."
    )
    parser.add_argument("--batch-json", type=Path, required=True)
    parser.add_argument("--master-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--context-radius", type=int, default=1)
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "curation_id",
        "part_name",
        "quality_label",
        "selection_mode",
        "review_action",
        "source_clip",
        "start",
        "end",
        "match_score",
        "english_text",
        "chinese_text",
        "prev_context",
        "next_context",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "curation_id": row["curation_id"],
                    "part_name": row["part_name"],
                    "quality_label": row["quality_label"],
                    "selection_mode": row["selection_mode"],
                    "review_action": row["review_action"],
                    "source_clip": row["source_clip"],
                    "start": row["start"],
                    "end": row["end"],
                    "match_score": row["match_score"],
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                    "prev_context": " || ".join(row["prev_context"]),
                    "next_context": " || ".join(row["next_context"]),
                }
            )


def compact_segment(seg: dict[str, Any]) -> str:
    return f"{seg['start']:.1f}-{seg['end']:.1f} | {seg['english_text']} => {seg['chinese_text']}"


def recommend_action(row: dict[str, Any]) -> str:
    if row["quality_label"] == "phase-b-partial":
        return "confirm_partial_alignment"
    if row["selection_mode"] in {"manual-override", "manual-replacement", "manual-text-cleanup"}:
        return "check_wording_and_merge"
    if row["selection_mode"] == "anchor-fallback":
        return "confirm_anchor_alignment"
    return "spot_check_low_score"


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {payload['batch_name']} Context Pack",
        "",
        f"- Item count: `{payload['item_count']}`",
        f"- Scope note: `{payload['scope_note']}`",
        f"- Source batch: `{payload['source_batch_json']}`",
        "",
    ]
    for item in payload["items"]:
        lines.extend(
            [
                f"## {item['curation_id']} {item['part_name']}",
                "",
                f"- Review action: `{item['review_action']}`",
                f"- Selection mode: `{item['selection_mode']}`",
                f"- Match score: `{item['match_score']}`",
                f"- Source clip: `{item['source_clip']}`",
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
    batch_payload = json.loads(args.batch_json.read_text(encoding="utf-8"))
    master_payload = json.loads(args.master_json.read_text(encoding="utf-8"))

    batch_items = list(batch_payload.get("items") or [])
    master_segments = list(master_payload.get("segments") or [])

    by_part: dict[str, list[dict[str, Any]]] = {}
    for seg in master_segments:
        by_part.setdefault(seg["part_name"], []).append(seg)
    for segs in by_part.values():
        segs.sort(key=lambda item: (item["start"], item["end"], item["global_segment_id"]))

    items: list[dict[str, Any]] = []
    for row in batch_items:
        part_segments = by_part[row["part_name"]]
        index = next(i for i, seg in enumerate(part_segments) if seg["global_segment_id"] == row["global_segment_id"])
        prev_segments = part_segments[max(0, index - args.context_radius):index]
        next_segments = part_segments[index + 1:index + 1 + args.context_radius]
        items.append(
            {
                **row,
                "review_action": recommend_action(row),
                "prev_context": [compact_segment(seg) for seg in prev_segments],
                "next_context": [compact_segment(seg) for seg in next_segments],
            }
        )

    payload = {
        "version": "phase-b-batch-context-pack-v1",
        "batch_name": batch_payload["name"],
        "scope_note": batch_payload.get("scope_note", ""),
        "source_batch_json": str(args.batch_json),
        "source_master_json": str(args.master_json),
        "item_count": len(items),
        "items": items,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "context_items.json", payload)
    write_tsv(args.output_dir / "context_items.tsv", items)
    (args.output_dir / "README.md").write_text(build_markdown(payload), encoding="utf-8")
    print(f"wrote batch context pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
