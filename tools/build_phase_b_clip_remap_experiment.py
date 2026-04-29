from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a constrained remap experiment over top semantic clip-to-part candidates."
    )
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=Path("scratch/phase_b_semantic_v4/clip_part_mapping.json"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_clip_remap_experiment_v1.json"),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--duration-weight",
        type=float,
        default=0.00008,
        help="Penalty weight for absolute duration gaps.",
    )
    return parser.parse_args()


def build_choice_space(mapping: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
    choices: list[dict[str, Any]] = []
    for clip in mapping["clips"]:
        candidates = []
        for cand in clip["semantic_candidates"][:top_k]:
            candidates.append(
                {
                    "part_name": cand["part_name"],
                    "score": float(cand["score"]),
                }
            )
        seen = {cand["part_name"] for cand in candidates}
        if clip["assigned_part"] not in seen:
            candidates.append(
                {
                    "part_name": clip["assigned_part"],
                    "score": float(clip["semantic_assigned_score"]),
                }
            )
        choices.append(
            {
                "clip_name": clip["clip_name"],
                "clip_duration": float(clip["clip_duration"]),
                "current_part": clip["assigned_part"],
                "candidates": candidates,
            }
        )
    return choices


def evaluate_assignment(
    pick_indices: tuple[int, ...],
    choice_space: list[dict[str, Any]],
    target_durations: dict[str, float],
    duration_weight: float,
) -> dict[str, Any]:
    part_totals = {part: 0.0 for part in target_durations}
    semantic_total = 0.0
    assignments: list[dict[str, Any]] = []
    for choice, pick_index in zip(choice_space, pick_indices):
        candidate = choice["candidates"][pick_index]
        semantic_total += float(candidate["score"])
        part_totals[candidate["part_name"]] += float(choice["clip_duration"])
        assignments.append(
            {
                "clip_name": choice["clip_name"],
                "assigned_part": candidate["part_name"],
                "score": round(float(candidate["score"]), 4),
                "current_part": choice["current_part"],
            }
        )
    duration_gap_sum = 0.0
    part_stats = []
    for part_name, target in target_durations.items():
        assigned = part_totals[part_name]
        gap = assigned - target
        duration_gap_sum += abs(gap)
        part_stats.append(
            {
                "part_name": part_name,
                "target_cut_duration": round(target, 3),
                "assigned_clip_duration": round(assigned, 3),
                "duration_gap_seconds": round(gap, 3),
            }
        )
    objective = semantic_total - duration_weight * duration_gap_sum
    return {
        "objective": objective,
        "semantic_total": semantic_total,
        "duration_gap_sum": duration_gap_sum,
        "part_stats": part_stats,
        "assignments": assignments,
    }


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8"))
    target_durations = {
        part["part_name"]: float(part["cut_duration_target"]) for part in mapping["parts"]
    }
    choice_space = build_choice_space(mapping, top_k=args.top_k)

    candidate_lengths = [len(item["candidates"]) for item in choice_space]
    combos = itertools.product(*(range(length) for length in candidate_lengths))
    best: list[dict[str, Any]] = []
    current_picks = []
    for item in choice_space:
        current_parts = [cand["part_name"] for cand in item["candidates"]]
        current_picks.append(current_parts.index(item["current_part"]))
    baseline = evaluate_assignment(tuple(current_picks), choice_space, target_durations, args.duration_weight)

    for combo in combos:
        result = evaluate_assignment(combo, choice_space, target_durations, args.duration_weight)
        best.append(result)
        best.sort(key=lambda item: item["objective"], reverse=True)
        if len(best) > 8:
            best.pop()

    payload = {
        "version": "phase-b-clip-remap-experiment-v1",
        "source_mapping": str(args.mapping_json),
        "top_k": args.top_k,
        "duration_weight": args.duration_weight,
        "baseline": baseline,
        "best_candidates": best,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.output_json}")


if __name__ == "__main__":
    main()
