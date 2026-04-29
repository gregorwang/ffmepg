from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an editable review patch template from a Phase B review round JSON."
    )
    parser.add_argument("--round-json", type=Path, required=True, help="Round JSON from phase_b_review_rounds_v1.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for the review patch template.")
    parser.add_argument(
        "--template-version",
        type=str,
        default="phase-b-review-patch-template-v1",
        help="Version label written into the template manifest.",
    )
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "patch_id",
        "global_segment_id",
        "part_name",
        "review_action",
        "current_status",
        "decision",
        "notes",
        "english_text",
        "chinese_text",
        "revised_english_text",
        "revised_chinese_text",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "patch_id": row["patch_id"],
                    "global_segment_id": row["global_segment_id"],
                    "part_name": row["part_name"],
                    "review_action": row["review_action"],
                    "current_status": row["current_status"],
                    "decision": row["decision"],
                    "notes": row["notes"],
                    "english_text": row["current_segment"]["english_text"],
                    "chinese_text": row["current_segment"]["chinese_text"],
                    "revised_english_text": row["revised_fields"]["english_text"],
                    "revised_chinese_text": row["revised_fields"]["chinese_text"],
                }
            )


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Phase B Review Patch Template",
        "",
        f"- Template version: `{manifest['template_version']}`",
        f"- Round name: `{manifest['round_name']}`",
        f"- Source round json: `{manifest['source_round_json']}`",
        f"- Item count: `{manifest['item_count']}`",
        "",
        "## How to use",
        "",
        "1. Edit `template.json` as the source of truth.",
        "2. For each item, set `decision` to one of:",
        "   - `pending`",
        "   - `confirmed`",
        "   - `revised`",
        "   - `excluded`",
        "   - `split`",
        "3. Use `revised_fields` only when `decision=revised`.",
        "4. Use `split_segments` only when `decision=split`.",
        "5. `template.tsv` is only a convenience view; the merge script reads `template.json`.",
        "",
        "## Notes",
        "",
        "- `current_segment` is copied from the current automatic baseline.",
        "- `review_action` and context fields are preserved to reduce context-switching during manual review.",
        "- A later merge step will write confirmed/revised/excluded/split decisions back into the reviewed master.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_patch_entry(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "patch_id": f"patch_{index:04d}",
        "curation_id": item["curation_id"],
        "global_segment_id": item["global_segment_id"],
        "part_name": item["part_name"],
        "priority": item["priority"],
        "review_action": item.get("review_action", "general_review"),
        "reason_tags": list(item.get("reason_tags") or []),
        "current_status": item.get("current_status", "needs-review"),
        "decision": "pending",
        "notes": "",
        "current_segment": {
            "source_clip": item["source_clip"],
            "start": item["start"],
            "end": item["end"],
            "duration": item["duration"],
            "match_score": item["match_score"],
            "selection_mode": item["selection_mode"],
            "quality_label": item["quality_label"],
            "english_cue_ids": list(item.get("english_cue_ids") or []),
            "chinese_cue_ids": list(item.get("chinese_cue_ids") or []),
            "english_text": item["english_text"],
            "chinese_text": item["chinese_text"],
            "review_status": item.get("current_status", "needs-review"),
            "review_notes": item.get("review_notes", ""),
        },
        "revised_fields": {
            "source_clip": item["source_clip"],
            "start": item["start"],
            "end": item["end"],
            "duration": item["duration"],
            "match_score": item["match_score"],
            "selection_mode": "manual-review-revised",
            "alignment_type": item.get("alignment_type", ""),
            "english_cue_ids": list(item.get("english_cue_ids") or []),
            "chinese_cue_ids": list(item.get("chinese_cue_ids") or []),
            "english_text": item["english_text"],
            "chinese_text": item["chinese_text"],
        },
        "split_segments": [],
        "prev_context": list(item.get("prev_context") or []),
        "next_context": list(item.get("next_context") or []),
    }


def main() -> None:
    args = parse_args()
    payload = json.loads(args.round_json.read_text(encoding="utf-8"))
    items = list(payload.get("items") or [])
    round_name = args.round_json.stem

    patch_entries = [build_patch_entry(item, index) for index, item in enumerate(items, start=1)]
    manifest = {
        "template_version": args.template_version,
        "source_round_json": str(args.round_json),
        "round_name": round_name,
        "item_count": len(patch_entries),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "template.json", {"manifest": manifest, "items": patch_entries})
    write_tsv(args.output_dir / "template.tsv", patch_entries)
    write_readme(args.output_dir / "README.md", manifest)
    print(f"wrote review patch template -> {args.output_dir}")


if __name__ == "__main__":
    main()
