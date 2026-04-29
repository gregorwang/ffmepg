from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_SHORTLIST_TSV = Path("scratch/phase_c_clip_review_shortlist_v2/shortlist.tsv")
DEFAULT_BUNDLE_ROOT = Path("scratch/phase_c_clip_review_bundles_v1")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_shortlist_context_pack_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export context packs for shortlisted Phase C clip candidates.")
    parser.add_argument("--shortlist-tsv", type=Path, default=DEFAULT_SHORTLIST_TSV)
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--english-context", type=int, default=2)
    parser.add_argument("--chinese-context", type=int, default=3)
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


def main() -> None:
    args = parse_args()
    shortlist_rows = load_tsv(args.shortlist_tsv)
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in shortlist_rows:
        grouped.setdefault(row["clip_name"], []).append(row)

    manifest_rows: list[dict[str, Any]] = []
    all_card_rows: list[dict[str, Any]] = []

    for clip_name, clip_rows in grouped.items():
        bundle_path = args.bundle_root / clip_name / "bundle.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        review_rows = list(bundle["review_rows"])
        chinese_cues = list(bundle["chinese_cues"])
        english_index = {row["english_cue_id"]: idx for idx, row in enumerate(review_rows)}

        cards: list[dict[str, Any]] = []
        for item in clip_rows:
            start_idx = english_index[item["english_start_cue_id"]]
            end_idx = english_index[item["english_end_cue_id"]]
            english_context_start = max(0, start_idx - args.english_context)
            english_context_end = min(len(review_rows), end_idx + args.english_context + 1)

            cue_indices = [int(part) for part in item["candidate_cue_indices"].split(",") if part.strip()]
            chinese_positions = {
                int(row["cue_index"]): idx
                for idx, row in enumerate(chinese_cues)
            }
            zh_start = min(chinese_positions.get(cue_indices[0], 0), chinese_positions.get(cue_indices[-1], 0)) if cue_indices else 0
            zh_end = max(chinese_positions.get(cue_indices[0], 0), chinese_positions.get(cue_indices[-1], 0)) if cue_indices else 0
            chinese_context_start = max(0, zh_start - args.chinese_context)
            chinese_context_end = min(len(chinese_cues), zh_end + args.chinese_context + 1)

            card = {
                "clip_name": clip_name,
                "priority": item["priority"],
                "block_id": item["block_id"],
                "candidate_score": float(item["candidate_score"]),
                "english_count": int(item["english_count"]),
                "candidate_chinese_count": int(item["candidate_chinese_count"]),
                "candidate_cue_indices": item["candidate_cue_indices"],
                "english_text": item["english_text"],
                "chinese_text": item["chinese_text"],
                "english_context_rows": review_rows[english_context_start:english_context_end],
                "chinese_context_rows": chinese_cues[chinese_context_start:chinese_context_end],
            }
            cards.append(card)
            all_card_rows.append(
                {
                    "clip_name": clip_name,
                    "priority": item["priority"],
                    "block_id": item["block_id"],
                    "candidate_score": item["candidate_score"],
                    "english_count": item["english_count"],
                    "candidate_chinese_count": item["candidate_chinese_count"],
                    "candidate_cue_indices": item["candidate_cue_indices"],
                    "english_text": item["english_text"],
                    "chinese_text": item["chinese_text"],
                }
            )

        clip_dir = args.output_dir / clip_name
        write_json(clip_dir / "context_cards.json", {"clip_name": clip_name, "cards": cards})
        write_tsv(
            clip_dir / "context_cards.tsv",
            [row for row in all_card_rows if row["clip_name"] == clip_name],
            [
                "clip_name",
                "priority",
                "block_id",
                "candidate_score",
                "english_count",
                "candidate_chinese_count",
                "candidate_cue_indices",
                "english_text",
                "chinese_text",
            ],
        )
        manifest_rows.append({"clip_name": clip_name, "card_count": len(cards)})

    write_json(args.output_dir / "manifest.json", {"clip_count": len(manifest_rows), "clips": manifest_rows})
    write_tsv(
        args.output_dir / "context_cards.tsv",
        all_card_rows,
        [
            "clip_name",
            "priority",
            "block_id",
            "candidate_score",
            "english_count",
            "candidate_chinese_count",
            "candidate_cue_indices",
            "english_text",
            "chinese_text",
        ],
    )
    print(f"wrote context pack -> {args.output_dir}")


if __name__ == "__main__":
    main()
