from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


_BETWEEN_RE = re.compile(r"between\(t,([0-9]+(?:\.[0-9]+)?),([0-9]+(?:\.[0-9]+)?)\)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Ghost of Yotei Phase B transcript/selection metadata.")
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    summary = build_summary(args.scratch_root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def build_summary(scratch_root: Path) -> dict[str, Any]:
    part_dirs = sorted(path for path in scratch_root.glob("ghost-yotei-part*") if path.is_dir())
    return {
        "scratch_root": str(scratch_root),
        "part_count": len(part_dirs),
        "parts": [summarize_part(path) for path in part_dirs],
    }


def summarize_part(part_dir: Path) -> dict[str, Any]:
    transcript_path = _pick_first(
        part_dir,
        [
            "transcript.tightened*.json",
            "transcript*.json",
        ],
    )
    selection_path = _pick_first(
        part_dir,
        [
            "selection.vad-g3.json",
            "selection.vad.json",
            "selection.json",
            "selection*.json",
        ],
    )
    filter_path = _pick_filter_file(part_dir)
    project_path = _pick_first(
        part_dir,
        [
            "*.atproj",
        ],
    )

    transcript_summary = summarize_transcript(transcript_path)
    selection_summary = summarize_selection(selection_path, transcript_summary["segment_ids"]) if selection_path else None
    filter_summary = summarize_filter(filter_path) if filter_path else None
    project_summary = summarize_project(project_path) if project_path else None
    transcript_output = dict(transcript_summary)
    transcript_output.pop("segment_ids", None)

    return {
        "part": part_dir.name,
        "transcript": transcript_output,
        "selection": selection_summary,
        "filter": filter_summary,
        "project": project_summary,
    }


def summarize_transcript(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "path": None,
            "segment_count": 0,
            "segment_ids": [],
            "segment_id_preview": [],
            "first_start": None,
            "last_end": None,
        }

    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    segments = payload.get("Segments") or payload.get("segments") or []
    segment_ids = [str(item.get("Id") or item.get("id") or "") for item in segments if item.get("Id") or item.get("id")]
    starts = [float(item.get("Start") or item.get("start") or 0.0) for item in segments]
    ends = [float(item.get("End") or item.get("end") or item.get("Start") or item.get("start") or 0.0) for item in segments]

    return {
        "path": str(path),
        "segment_count": len(segments),
        "segment_ids": segment_ids,
        "segment_id_preview": segment_ids[:10],
        "first_start": round(min(starts), 3) if starts else None,
        "last_end": round(max(ends), 3) if ends else None,
    }


def summarize_selection(path: Path, transcript_ids: list[str]) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    items = payload.get("TargetSegments") or payload.get("targetSegments") or []
    selected_ids = [
        str(item.get("SegmentId") or item.get("segmentId") or "")
        for item in items
        if (item.get("SegmentId") or item.get("segmentId"))
    ]
    transcript_id_set = set(transcript_ids)
    matched = [segment_id for segment_id in selected_ids if segment_id in transcript_id_set]
    unmatched = [segment_id for segment_id in selected_ids if segment_id not in transcript_id_set]

    return {
        "path": str(path),
        "selected_count": len(selected_ids),
        "matched_transcript_count": len(matched),
        "unmatched_transcript_count": len(unmatched),
        "selected_preview": selected_ids[:10],
        "unmatched_preview": unmatched[:10],
    }


def summarize_filter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    intervals = [(float(start), float(end)) for start, end in _BETWEEN_RE.findall(text)]
    total_seconds = sum(max(0.0, end - start) for start, end in intervals)
    return {
        "path": str(path),
        "interval_count": len(intervals),
        "kept_seconds": round(total_seconds, 3),
        "first_intervals": [
            {
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(max(0.0, end - start), 3),
            }
            for start, end in intervals[:10]
        ],
    }


def summarize_project(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return {
        "path": str(path),
        "input_path": str(payload.get("InputPath") or ""),
        "working_audio_path": str(payload.get("WorkingAudioPath") or ""),
        "transcript_path": str(payload.get("TranscriptPath") or ""),
        "selection_path": str(payload.get("SelectionPath") or ""),
        "status": str(payload.get("Status") or ""),
    }


def _pick_first(directory: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        matches = sorted(directory.glob(pattern))
        if matches:
            return matches[0]
    return None


def _pick_filter_file(directory: Path) -> Path | None:
    preferred = sorted(
        path
        for path in directory.glob("*.filter.txt")
        if "audio-concat" not in path.name.lower()
    )
    if preferred:
        return preferred[0]
    fallback = sorted(directory.glob("*.filter.txt"))
    return fallback[0] if fallback else None


if __name__ == "__main__":
    main()
