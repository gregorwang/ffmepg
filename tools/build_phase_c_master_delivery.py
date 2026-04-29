from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_DELIVERY_PACK_DIR = Path("scratch/phase_c_delivery_pack_v1_complete")
DEFAULT_APPLIED_DIR = Path("scratch/phase_c_predecision_applied_v3_complete")
DEFAULT_BURNIN_DIR = Path("scratch/phase_c_burnin_prep_v3_complete")
DEFAULT_DELTA_DIR = Path("scratch/phase_c_predecision_delta_pack_v4_complete_vs_base")
DEFAULT_HANDOFF_JSON = Path("scratch/phase_c_model_handoff_v3_complete/handoff.json")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_master_delivery_v1_complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a single-entry master delivery index for the completed Phase C output.")
    parser.add_argument("--delivery-pack-dir", type=Path, default=DEFAULT_DELIVERY_PACK_DIR)
    parser.add_argument("--applied-dir", type=Path, default=DEFAULT_APPLIED_DIR)
    parser.add_argument("--burnin-dir", type=Path, default=DEFAULT_BURNIN_DIR)
    parser.add_argument("--delta-dir", type=Path, default=DEFAULT_DELTA_DIR)
    parser.add_argument("--handoff-json", type=Path, default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Ghost Yotei Phase C Master Delivery",
        "",
        f"- Delivery pack: `{manifest['delivery_pack_dir']}`",
        f"- Applied dir: `{manifest['applied_dir']}`",
        f"- Burn-in dir: `{manifest['burnin_dir']}`",
        f"- Delta dir: `{manifest['delta_dir']}`",
        f"- Handoff json: `{manifest['handoff_json']}`",
        "",
        "## Summary",
        "",
        f"- Total cues: `{manifest['total_cue_count']}`",
        f"- Matched cues: `{manifest['matched_cue_count']}`",
        f"- Unmatched cues: `{manifest['unmatched_cue_count']}`",
        f"- Coverage ratio: `{manifest['coverage_ratio']}`",
        f"- Remaining model requests: `{manifest['remaining_model_requests']}`",
        "",
        "## Notes",
        "",
        "- This directory is an index pack. It does not duplicate the large payload files.",
        "- Use `paths.tsv` when you want one machine-readable table of final artifact entry points.",
        "- Use `parts.tsv` when you want per-part completion statistics only.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    delivery_manifest = load_json(args.delivery_pack_dir / "manifest.json")
    applied_manifest = load_json(args.applied_dir / "manifest.json")
    burnin_manifest = load_json(args.burnin_dir / "manifest.json")
    delta_manifest = load_json(args.delta_dir / "manifest.json")
    handoff = load_json(args.handoff_json)

    part_rows = [
        {
            "part_name": row["part_name"],
            "short_name": row["short_name"],
            "segment_count": row["segment_count"],
            "matched_count": row["matched_count"],
            "unmatched_count": row["unmatched_count"],
            "coverage_ratio": row["coverage_ratio"],
        }
        for row in delivery_manifest.get("part_stats") or []
    ]

    path_rows = [
        {"artifact": "delivery_pack_dir", "path": str(args.delivery_pack_dir), "note": "Main delivery package"},
        {"artifact": "delivery_manifest", "path": str(args.delivery_pack_dir / "manifest.json"), "note": "Delivery package manifest"},
        {"artifact": "applied_dir", "path": str(args.applied_dir), "note": "Full applied Phase C output"},
        {"artifact": "applied_manifest", "path": str(args.applied_dir / "manifest.json"), "note": "Applied output manifest"},
        {"artifact": "burnin_dir", "path": str(args.burnin_dir), "note": "Bilingual SRT and ffmpeg commands"},
        {"artifact": "burnin_manifest", "path": str(args.burnin_dir / "manifest.json"), "note": "Burn-in prep manifest"},
        {"artifact": "delta_dir", "path": str(args.delta_dir), "note": "Delta against original Phase C base"},
        {"artifact": "delta_manifest", "path": str(args.delta_dir / "manifest.json"), "note": "Delta manifest"},
        {"artifact": "handoff_json", "path": str(args.handoff_json), "note": "Completion handoff summary"},
        {"artifact": "matched_segments", "path": str(args.delivery_pack_dir / "matched_segments.tsv"), "note": "Only matched rows"},
        {"artifact": "unmatched_segments", "path": str(args.delivery_pack_dir / "unmatched_segments.tsv"), "note": "Closed unmatched rows"},
    ]

    remaining_requests = int((handoff.get("current_round") or {}).get("request_count") or 0)
    manifest = {
        "delivery_pack_dir": str(args.delivery_pack_dir),
        "applied_dir": str(args.applied_dir),
        "burnin_dir": str(args.burnin_dir),
        "delta_dir": str(args.delta_dir),
        "handoff_json": str(args.handoff_json),
        "source_version": applied_manifest.get("version"),
        "total_cue_count": delivery_manifest.get("total_cue_count"),
        "matched_cue_count": delivery_manifest.get("matched_cue_count"),
        "unmatched_cue_count": delivery_manifest.get("unmatched_cue_count"),
        "coverage_ratio": delivery_manifest.get("coverage_ratio"),
        "remaining_model_requests": remaining_requests,
        "decision_counts": dict((handoff.get("current_round") or {}).get("decision_counts") or {}),
        "changed_row_count_vs_base": delta_manifest.get("changed_row_count"),
        "burnin_part_count": burnin_manifest.get("part_count"),
        "next_action": handoff.get("next_action"),
    }

    write_json(args.output_dir / "manifest.json", manifest)
    write_tsv(args.output_dir / "parts.tsv", part_rows, ["part_name", "short_name", "segment_count", "matched_count", "unmatched_count", "coverage_ratio"])
    write_tsv(args.output_dir / "paths.tsv", path_rows, ["artifact", "path", "note"])
    write_json(args.output_dir / "handoff_snapshot.json", handoff)
    write_readme(args.output_dir / "README.md", manifest)
    print(f"wrote phase c master delivery -> {args.output_dir}")


if __name__ == "__main__":
    main()
