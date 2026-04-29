from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

from phase_b_sequence_align import extract_english_speakers


DEFAULT_CANDIDATE_ROOT = Path("scratch/phase_c_clip_candidate_packs_v1")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_clip_review_shortlist_v1")
_ZH_SPEAKER_CAPTURE_RE = re.compile(r"([^：:\s]{1,12})[：:]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a prioritized review shortlist from Phase C clip candidate packs.")
    parser.add_argument("--candidate-root", type=Path, default=DEFAULT_CANDIDATE_ROOT)
    parser.add_argument("--clips", nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--high-score", type=float, default=0.58)
    parser.add_argument("--medium-score", type=float, default=0.54)
    parser.add_argument("--max-english-count", type=int, default=6)
    parser.add_argument("--max-candidate-chinese-count", type=int, default=4)
    parser.add_argument("--top-k-per-clip", type=int, default=40)
    parser.add_argument("--min-score-gap", type=float, default=0.03)
    return parser.parse_args()


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


def classify_priority(score: float, english_count: int, candidate_chinese_count: int, high_score: float, medium_score: float) -> str | None:
    if english_count <= 3 and candidate_chinese_count <= 3 and score >= high_score:
        return "high"
    if english_count <= 6 and candidate_chinese_count <= 4 and score >= medium_score:
        return "medium"
    return None


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def extract_chinese_speakers(text: str) -> set[str]:
    return {match.strip() for match in _ZH_SPEAKER_CAPTURE_RE.findall(text or "") if match.strip()}


def speaker_gate(english_text: str, chinese_text: str) -> str | None:
    english_speakers = extract_english_speakers(english_text)
    chinese_speakers = extract_chinese_speakers(chinese_text)
    if not english_speakers or not chinese_speakers:
        return None
    overlap = english_speakers & chinese_speakers
    if not overlap:
        return "speaker-disjoint"
    if len(english_speakers) <= 1 and len(chinese_speakers) > 1:
        extras = chinese_speakers - english_speakers
        if extras:
            return "speaker-multi-mismatch"
    if len(chinese_speakers) >= 3 and (len(overlap) / len(chinese_speakers)) < 0.5:
        return "speaker-low-overlap"
    return None


def text_shape_gate(chinese_text: str) -> str | None:
    text = (chinese_text or "").strip()
    if "·" in text and "：" not in text and ":" not in text:
        return "label-fragment"
    return None


def main() -> None:
    args = parse_args()
    all_rows: list[dict[str, Any]] = []
    clip_manifests: list[dict[str, Any]] = []

    for clip_name in args.clips:
        clip_dir = args.candidate_root / clip_name
        manifest = json.loads((clip_dir / "manifest.json").read_text(encoding="utf-8"))
        candidate_rows = load_tsv(clip_dir / "candidate_rows.tsv")
        block_rows = {row["block_id"]: row for row in load_tsv(clip_dir / "candidate_blocks.tsv")}

        rows_by_block: dict[str, list[dict[str, str]]] = {}
        for row in candidate_rows:
            block_id = row["block_id"]
            rows_by_block.setdefault(block_id, []).append(row)

        shortlisted: list[dict[str, Any]] = []
        skip_counts: dict[str, int] = {}
        for block_id, rows in rows_by_block.items():
            rows = sorted(rows, key=lambda item: float(item["candidate_score"]), reverse=True)
            row = rows[0]
            score = float(row["candidate_score"])
            second_score = float(rows[1]["candidate_score"]) if len(rows) > 1 else float("-inf")
            score_gap = math.inf if len(rows) <= 1 else score - second_score
            english_count = int(row["english_count"])
            candidate_chinese_count = int(row["candidate_chinese_count"])
            if english_count > args.max_english_count or candidate_chinese_count > args.max_candidate_chinese_count:
                skip_counts["size-limit"] = skip_counts.get("size-limit", 0) + 1
                continue
            priority = classify_priority(
                score=score,
                english_count=english_count,
                candidate_chinese_count=candidate_chinese_count,
                high_score=args.high_score,
                medium_score=args.medium_score,
            )
            if priority is None:
                skip_counts["score-threshold"] = skip_counts.get("score-threshold", 0) + 1
                continue
            if score_gap < args.min_score_gap:
                skip_counts["low-score-gap"] = skip_counts.get("low-score-gap", 0) + 1
                continue
            speaker_gate_reason = speaker_gate(row["english_text"], row["chinese_text"])
            if speaker_gate_reason:
                skip_counts[speaker_gate_reason] = skip_counts.get(speaker_gate_reason, 0) + 1
                continue
            text_shape_reason = text_shape_gate(row["chinese_text"])
            if text_shape_reason:
                skip_counts[text_shape_reason] = skip_counts.get(text_shape_reason, 0) + 1
                continue
            block_meta = block_rows[block_id]
            shortlisted.append(
                {
                    "clip_name": clip_name,
                    "priority": priority,
                    "block_id": block_id,
                    "english_start_cue_id": row["english_start_cue_id"],
                    "english_end_cue_id": row["english_end_cue_id"],
                    "english_count": english_count,
                    "candidate_score": score,
                    "score_gap": round(score_gap, 4) if math.isfinite(score_gap) else "",
                    "candidate_chinese_count": candidate_chinese_count,
                    "candidate_cue_indices": row["candidate_cue_indices"],
                    "english_text": row["english_text"],
                    "chinese_text": row["chinese_text"],
                    "estimated_chinese_preview": block_meta["estimated_chinese_preview"],
                }
            )

        shortlisted.sort(key=lambda item: (item["priority"] != "high", -item["candidate_score"], item["block_id"]))
        shortlisted = shortlisted[: args.top_k_per_clip]
        all_rows.extend(shortlisted)
        clip_manifests.append(
            {
                "clip_name": clip_name,
                "shortlist_count": len(shortlisted),
                "priority_counts": {
                    "high": sum(1 for row in shortlisted if row["priority"] == "high"),
                    "medium": sum(1 for row in shortlisted if row["priority"] == "medium"),
                },
                "skip_counts": dict(sorted(skip_counts.items())),
            }
        )

    all_rows.sort(key=lambda item: (item["clip_name"], item["priority"] != "high", -item["candidate_score"], item["block_id"]))
    manifest = {
        "clip_count": len(clip_manifests),
        "row_count": len(all_rows),
        "clips": clip_manifests,
    }
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "shortlist.json", {"manifest": manifest, "rows": all_rows})
    write_tsv(
        args.output_dir / "shortlist.tsv",
        all_rows,
        [
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
        ],
    )
    print(f"wrote shortlist -> {args.output_dir}")


if __name__ == "__main__":
    main()
