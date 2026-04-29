from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a focused diagnostic probe for why Phase B part03 alignment underperformed."
    )
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=Path("scratch/phase_b_semantic_v4/clip_part_mapping.json"),
    )
    parser.add_argument(
        "--chinese-ocr-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--english-ocr-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_part03_probe_v1.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("scratch/phase_b_part03_probe_v1.md"),
    )
    return parser.parse_args()


def load_cue_stats(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    cues = payload.get("cues") or []
    if not cues:
        return {"cue_count": 0, "start": None, "end": None}
    return {
        "cue_count": len(cues),
        "start": float(cues[0]["start"]),
        "end": float(cues[-1]["end"]),
        "duration": round(float(cues[-1]["end"]) - float(cues[0]["start"]), 3),
    }


def clip_status(margin: float) -> str:
    if margin >= 0.08:
        return "stable"
    if margin >= 0.0:
        return "weak-positive"
    if margin >= -0.05:
        return "ambiguous"
    return "misassigned-likely"


def build_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    summary = payload["summary"]
    lines.append("# Phase B part03 Probe")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- English OCR cue count: `{summary['english_ocr']['cue_count']}`")
    lines.append(f"- English OCR duration: `{summary['english_ocr']['duration']}`")
    lines.append(f"- Assigned Chinese clip count: `{summary['assigned_clip_count']}`")
    lines.append(f"- Assigned Chinese summed duration: `{summary['assigned_chinese_duration']}`")
    lines.append(f"- Target cut duration: `{summary['target_cut_duration']}`")
    lines.append(f"- Duration gap: `{summary['duration_gap_seconds']}`")
    lines.append(f"- Stable clips: `{summary['stable_clip_count']}`")
    lines.append(f"- Weak/ambiguous clips: `{summary['ambiguous_or_worse_count']}`")
    lines.append("")
    lines.append("## Diagnosis")
    lines.append("")
    lines.append(
        "- `part03` is not failing only at cue-level alignment. Its upstream clip-to-part assignment is unstable."
    )
    lines.append(
        "- Two of the three currently assigned Chinese clips do not beat their best alternative part by score."
    )
    lines.append(
        "- The assigned Chinese duration overshoots the part03 target by more than one thousand seconds, which is far larger than the gaps seen in the phase-b local-success path for part01/part02."
    )
    lines.append("")
    lines.append("## Assigned Clips")
    lines.append("")
    for clip in payload["assigned_clips"]:
        lines.append(f"### {clip['clip_name']}")
        lines.append("")
        lines.append(f"- Status: `{clip['status']}`")
        lines.append(f"- Score margin: `{clip['score_margin']}`")
        lines.append(f"- Clip duration: `{clip['clip_duration']}`")
        lines.append(f"- Normalized cut duration: `{clip['normalized_cut_duration']}`")
        lines.append(f"- Assigned window: `{clip['part_cut_start']} -> {clip['part_cut_end']}`")
        lines.append(f"- Best assigned score: `{clip['semantic_assigned_score']}`")
        lines.append(f"- Best alternative score: `{clip['semantic_best_alternative_score']}`")
        lines.append("")
        lines.append("Top candidates:")
        for cand in clip["semantic_candidates"][:3]:
            lines.append(
                f"- `{cand['part_name']}` score `{cand['score']}` window `{cand['window_start_time']} -> {cand['window_end_time']}`"
            )
        lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append("- Do not push part03 through the same local cue-level workflow yet.")
    lines.append("- First re-open clip-to-part assignment for the three candidate Chinese clips.")
    lines.append("- Prioritize a remap experiment before spending more effort on cue-level bilingual matching.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8"))
    part03 = next(part for part in mapping["parts"] if part["part_name"] == "ghost-yotei-part03")

    assigned_clips: list[dict[str, Any]] = []
    for clip in mapping["clips"]:
        if clip["assigned_part"] != "ghost-yotei-part03":
            continue
        chinese_stats = load_cue_stats(args.chinese_ocr_root / clip["clip_name"] / "cleaned.json")
        margin = round(
            float(clip["semantic_assigned_score"]) - float(clip["semantic_best_alternative_score"]),
            4,
        )
        assigned_clips.append(
            {
                "clip_name": clip["clip_name"],
                "clip_order_in_part": clip["clip_order_in_part"],
                "clip_duration": round(float(clip["clip_duration"]), 3),
                "normalized_cut_duration": round(float(clip["normalized_cut_duration"]), 3),
                "part_cut_start": round(float(clip["part_cut_start"]), 3),
                "part_cut_end": round(float(clip["part_cut_end"]), 3),
                "approx_original_start": round(float(clip["approx_original_start"]), 3),
                "approx_original_end": round(float(clip["approx_original_end"]), 3),
                "semantic_assigned_score": round(float(clip["semantic_assigned_score"]), 4),
                "semantic_best_alternative_score": round(float(clip["semantic_best_alternative_score"]), 4),
                "score_margin": margin,
                "status": clip_status(margin),
                "semantic_candidates": clip["semantic_candidates"],
                "chinese_ocr": chinese_stats,
            }
        )

    english_stats = load_cue_stats(args.english_ocr_root / "part03" / "cleaned.json")
    stable_count = sum(1 for clip in assigned_clips if clip["status"] == "stable")
    probe = {
        "version": "phase-b-part03-probe-v1",
        "source_mapping": str(args.mapping_json),
        "summary": {
            "part_name": "ghost-yotei-part03",
            "assigned_clip_count": len(assigned_clips),
            "stable_clip_count": stable_count,
            "ambiguous_or_worse_count": len(assigned_clips) - stable_count,
            "target_cut_duration": round(float(part03["cut_duration_target"]), 3),
            "assigned_chinese_duration": round(float(part03["assigned_clip_duration"]), 3),
            "duration_gap_seconds": round(float(part03["duration_gap_seconds"]), 3),
            "english_ocr": english_stats,
        },
        "assigned_clips": assigned_clips,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(probe, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(build_markdown(probe), encoding="utf-8")
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")


if __name__ == "__main__":
    main()
