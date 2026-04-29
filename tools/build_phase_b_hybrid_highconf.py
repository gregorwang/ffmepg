from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


PART_POLICIES: dict[str, dict[str, Any]] = {
    "ghost-yotei-part01": {
        "version": "phase_b_sequence_mpnet_v2",
        "min_score": 0.80,
        "exclude_ids": [],
    },
    "ghost-yotei-part02": {
        "version": "phase_b_sequence_mpnet_v4",
        "min_score": 0.78,
        "exclude_ids": ["blk_0483"],
    },
    "ghost-yotei-part03": {
        "version": "phase_b_sequence_mpnet_v4",
        "min_score": 0.80,
        "exclude_ids": [],
    },
    "ghost-yotei-part04": {
        "version": "phase_b_sequence_mpnet_v2",
        "min_score": 0.80,
        "exclude_ids": [],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_part_map(sequence_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {part["part_name"]: part for part in sequence_doc["parts"]}


def select_segments(
    part_name: str,
    part_doc: dict[str, Any],
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    min_score = float(policy["min_score"])
    excluded_ids = set(policy.get("exclude_ids", []))
    selected: list[dict[str, Any]] = []
    for segment in part_doc["segments"]:
        score = segment.get("match_score")
        if score is None or score < min_score:
            continue
        if segment["id"] in excluded_ids:
            continue
        row = dict(segment)
        row["selection_version"] = policy["version"]
        row["selection_min_score"] = min_score
        selected.append(row)
    selected.sort(key=lambda item: item["match_score"], reverse=True)
    return selected


def build_output(scratch_root: Path) -> dict[str, Any]:
    cached_docs: dict[str, dict[str, Any]] = {}
    cached_part_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for version in sorted({policy["version"] for policy in PART_POLICIES.values()}):
        doc = load_json(scratch_root / version / "bilingual_alignment.sequence.json")
        cached_docs[version] = doc
        cached_part_maps[version] = iter_part_map(doc)

    parts: list[dict[str, Any]] = []
    flat_candidates: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    total_candidates = 0

    for part_name, policy in PART_POLICIES.items():
        version = policy["version"]
        part_doc = cached_part_maps[version][part_name]
        selected = select_segments(part_name, part_doc, policy)
        parts.append(
            {
                "part_name": part_name,
                "source_version": version,
                "selection_min_score": policy["min_score"],
                "excluded_ids": policy.get("exclude_ids", []),
                "segment_count": part_doc["segment_count"],
                "candidate_count": len(selected),
                "segments": selected,
            }
        )
        total_candidates += len(selected)
        scores = [item["match_score"] for item in selected]
        summary.append(
            {
                "part_name": part_name,
                "source_version": version,
                "selection_min_score": policy["min_score"],
                "segment_count": part_doc["segment_count"],
                "candidate_count": len(selected),
                "mean_match_score": round(mean(scores), 4) if scores else None,
            }
        )
        for item in selected:
            flat_row = dict(item)
            flat_row["part_name"] = part_name
            flat_candidates.append(flat_row)

    flat_candidates.sort(
        key=lambda item: (item["part_name"], item["start"], item["end"], item["id"])
    )

    return {
        "version": "phase-b-hybrid-highconf-v1",
        "alignment_strategy": "per-part sequence alignment hybrid, curated high-confidence subset",
        "selection_policy": PART_POLICIES,
        "total_candidate_count": total_candidates,
        "parts": parts,
        "summary": summary,
        "flat_candidates": flat_candidates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scratch-root",
        type=Path,
        default=Path("scratch"),
        help="Scratch directory containing phase_b_sequence_mpnet_v2/v4 outputs.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_bilingual_hybrid_highconf_v1.json"),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--output-tsv",
        type=Path,
        default=Path("scratch/phase_b_bilingual_hybrid_highconf_v1.tsv"),
        help="Flat TSV output path for review.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = build_output(args.scratch_root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    args.output_tsv.parent.mkdir(parents=True, exist_ok=True)
    tsv_lines = [
        "\t".join(
            [
                "part_name",
                "selection_version",
                "match_score",
                "id",
                "source_clip",
                "start",
                "end",
                "english_text",
                "chinese_text",
            ]
        )
    ]
    for item in output["flat_candidates"]:
        tsv_lines.append(
            "\t".join(
                [
                    str(item.get("part_name", "")),
                    str(item.get("selection_version", "")),
                    f"{item.get('match_score', 0):.4f}",
                    str(item.get("id", "")),
                    str(item.get("source_clip", "")),
                    str(item.get("start", "")),
                    str(item.get("end", "")),
                    str(item.get("english_text", "")).replace("\t", " ").replace("\n", " "),
                    str(item.get("chinese_text", "")).replace("\t", " ").replace("\n", " "),
                ]
            )
        )
    args.output_tsv.write_text("\n".join(tsv_lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_tsv}")
    for item in output["summary"]:
        print(
            item["part_name"],
            f"source={item['source_version']}",
            f"threshold={item['selection_min_score']}",
            f"candidates={item['candidate_count']}",
            f"mean={item['mean_match_score']}",
        )
    print(f"total_candidates={output['total_candidate_count']}")


if __name__ == "__main__":
    main()
