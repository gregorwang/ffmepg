from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_master_review_queue_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate Phase C shortlist batches into a single master review queue.")
    parser.add_argument(
        "--pair",
        nargs=2,
        metavar=("SHORTLIST_DIR", "CONTEXT_DIR"),
        action="append",
        required=True,
        help="Pair a shortlist directory with its matching context-pack directory.",
    )
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


def priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1}.get(priority, 9)


def main() -> None:
    args = parse_args()
    all_rows: list[dict[str, Any]] = []
    clip_counts: dict[str, int] = {}
    source_batches: list[dict[str, Any]] = []

    for index, (shortlist_dir_raw, context_dir_raw) in enumerate(args.pair, start=1):
        shortlist_dir = Path(shortlist_dir_raw)
        context_dir = Path(context_dir_raw)
        shortlist_manifest = load_json(shortlist_dir / "manifest.json")
        context_manifest = load_json(context_dir / "manifest.json")
        shortlist_rows = load_tsv(shortlist_dir / "shortlist.tsv")

        batch_label = f"batch_{index:02d}"
        source_batches.append(
            {
                "batch_label": batch_label,
                "shortlist_dir": str(shortlist_dir),
                "context_dir": str(context_dir),
                "shortlist_row_count": int(shortlist_manifest.get("row_count") or 0),
                "context_clip_count": int(context_manifest.get("clip_count") or 0),
            }
        )

        for row in shortlist_rows:
            clip_name = row["clip_name"]
            clip_counts[clip_name] = clip_counts.get(clip_name, 0) + 1
            all_rows.append(
                {
                    "batch_label": batch_label,
                    "source_shortlist_dir": str(shortlist_dir),
                    "source_context_dir": str(context_dir),
                    "clip_name": clip_name,
                    "priority": row["priority"],
                    "block_id": row["block_id"],
                    "english_start_cue_id": row["english_start_cue_id"],
                    "english_end_cue_id": row["english_end_cue_id"],
                    "english_count": int(row["english_count"]),
                    "candidate_score": float(row["candidate_score"]),
                    "score_gap": float(row["score_gap"]) if str(row.get("score_gap") or "").strip() else None,
                    "candidate_chinese_count": int(row["candidate_chinese_count"]),
                    "candidate_cue_indices": row["candidate_cue_indices"],
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                    "estimated_chinese_preview": row["estimated_chinese_preview"],
                    "clip_context_json": str(context_dir / clip_name / "context_cards.json"),
                    "clip_context_tsv": str(context_dir / clip_name / "context_cards.tsv"),
                }
            )

    all_rows.sort(
        key=lambda item: (
            priority_rank(str(item["priority"])),
            -float(item["candidate_score"]),
            float(item["score_gap"]) if item["score_gap"] is not None else -1.0,
            int(item["english_count"]),
            item["clip_name"],
            item["block_id"],
        )
    )
    for queue_rank, row in enumerate(all_rows, start=1):
        row["queue_rank"] = queue_rank

    clip_rows = [
        {
            "clip_name": clip_name,
            "queue_count": count,
        }
        for clip_name, count in sorted(clip_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    manifest = {
        "batch_count": len(source_batches),
        "row_count": len(all_rows),
        "clip_count": len(clip_rows),
        "source_batches": source_batches,
        "clips": clip_rows,
    }

    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "master_queue.json", {"manifest": manifest, "rows": all_rows})
    write_tsv(
        args.output_dir / "master_queue.tsv",
        all_rows,
        [
            "queue_rank",
            "batch_label",
            "clip_name",
            "priority",
            "block_id",
            "english_start_cue_id",
            "english_end_cue_id",
            "english_count",
            "candidate_score",
            "score_gap",
            "candidate_chinese_count",
            "candidate_cue_indices",
            "english_text",
            "chinese_text",
            "estimated_chinese_preview",
            "clip_context_json",
            "clip_context_tsv",
            "source_shortlist_dir",
            "source_context_dir",
        ],
    )
    print(f"wrote master queue -> {args.output_dir}")


if __name__ == "__main__":
    main()
