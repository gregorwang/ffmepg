from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_phase_b_cue_local_align import write_tsv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expand part03 high-confidence seeds with nearby lower-threshold rows."
    )
    parser.add_argument("--full-json", type=Path, required=True)
    parser.add_argument("--seed-json", type=Path, required=True)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_part03_seed_expansion_v1.json"),
    )
    parser.add_argument(
        "--output-tsv",
        type=Path,
        default=Path("scratch/phase_b_part03_seed_expansion_v1.tsv"),
    )
    parser.add_argument("--seed-threshold", type=float, default=0.80)
    parser.add_argument("--expand-threshold", type=float, default=0.78)
    parser.add_argument("--cluster-gap-seconds", type=float, default=20.0)
    parser.add_argument("--neighbor-padding-seconds", type=float, default=8.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    full = json.loads(args.full_json.read_text(encoding="utf-8"))
    seed = json.loads(args.seed_json.read_text(encoding="utf-8"))
    full_rows = sorted(full["flat_candidates"], key=lambda r: (r["start"], r["end"]))
    seed_rows = sorted(seed["segments"], key=lambda r: (r["start"], r["end"]))

    clusters: list[list[dict]] = []
    current: list[dict] = []
    for row in seed_rows:
        if not current or row["start"] - current[-1]["end"] <= args.cluster_gap_seconds:
            current.append(row)
        else:
            clusters.append(current)
            current = [row]
    if current:
        clusters.append(current)

    seed_keys = {(",".join(r["english_cue_ids"]), ",".join(r["chinese_cue_ids"])) for r in seed_rows}
    selected: list[dict] = list(seed_rows)
    selected_keys = set(seed_keys)

    for cluster in clusters:
        source_clip = cluster[0]["source_clip"]
        window_start = cluster[0]["start"] - args.neighbor_padding_seconds
        window_end = cluster[-1]["end"] + args.neighbor_padding_seconds
        for row in full_rows:
            key = (",".join(row["english_cue_ids"]), ",".join(row["chinese_cue_ids"]))
            if key in selected_keys:
                continue
            if row["source_clip"] != source_clip:
                continue
            if row["end"] < window_start or row["start"] > window_end:
                continue
            if float(row["match_score"]) < args.expand_threshold:
                continue
            selected.append(row)
            selected_keys.add(key)

    selected.sort(key=lambda r: (r["start"], r["end"], ",".join(r["english_cue_ids"])))
    payload = {
        "version": "phase-b-part03-seed-expansion-v1",
        "source_full_json": str(args.full_json),
        "source_seed_json": str(args.seed_json),
        "seed_threshold": args.seed_threshold,
        "expand_threshold": args.expand_threshold,
        "segment_count": len(selected),
        "segments": selected,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, selected)
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_tsv}")


if __name__ == "__main__":
    main()
