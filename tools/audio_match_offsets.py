from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import correlate


@dataclass(slots=True)
class MatchResult:
    clip_name: str
    part_name: str
    best_offset_seconds: float
    best_score: float
    search_start_seconds: float
    search_end_seconds: float
    clip_duration_seconds: float


def main() -> None:
    parser = argparse.ArgumentParser(description="Refine clip offsets within dialogue-cut parts via audio correlation.")
    parser.add_argument("--mapping-json", type=Path, required=True)
    parser.add_argument("--video-root", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--sample-rate", type=int, default=200)
    parser.add_argument("--padding-seconds", type=float, default=900.0)
    args = parser.parse_args()

    mapping = json.loads(args.mapping_json.read_text(encoding="utf-8-sig"))
    part_video_paths = discover_part_videos(args.scratch_root)
    part_audio_cache: dict[str, np.ndarray] = {}
    results: list[dict[str, Any]] = []

    for item in mapping.get("clips") or []:
        clip_name = str(item["clip_name"])
        part_name = str(item["assigned_part"])
        clip_path = args.video_root / f"{clip_name}.mp4"
        part_path = part_video_paths[part_name]

        clip_audio = load_audio_track(clip_path, sample_rate=args.sample_rate)
        part_audio = part_audio_cache.get(part_name)
        if part_audio is None:
            part_audio = load_audio_track(part_path, sample_rate=args.sample_rate)
            part_audio_cache[part_name] = part_audio

        clip_duration = len(clip_audio) / float(args.sample_rate)
        approx_start = float(item.get("part_cut_start") or 0.0)
        approx_end = float(item.get("part_cut_end") or approx_start + clip_duration)
        search_start = max(0.0, approx_start - args.padding_seconds)
        search_end = min((len(part_audio) / float(args.sample_rate)), approx_end + args.padding_seconds)
        matched = match_clip_within_part(
            clip_name=clip_name,
            clip_audio=clip_audio,
            part_name=part_name,
            part_audio=part_audio,
            sample_rate=args.sample_rate,
            search_start=search_start,
            search_end=search_end,
        )

        updated = dict(item)
        updated["audio_match"] = {
            "best_offset_seconds": round(matched.best_offset_seconds, 3),
            "best_score": round(matched.best_score, 4),
            "search_start_seconds": round(matched.search_start_seconds, 3),
            "search_end_seconds": round(matched.search_end_seconds, 3),
            "clip_duration_seconds": round(matched.clip_duration_seconds, 3),
        }
        updated["part_cut_start"] = round(matched.best_offset_seconds, 3)
        updated["part_cut_end"] = round(matched.best_offset_seconds + matched.clip_duration_seconds, 3)
        updated["approx_original_start"] = round(matched.best_offset_seconds, 3)
        updated["approx_original_end"] = round(matched.best_offset_seconds + matched.clip_duration_seconds, 3)
        results.append(updated)
        print(
            json.dumps(
                {
                    "clip_name": clip_name,
                    "part_name": part_name,
                    "best_offset_seconds": round(matched.best_offset_seconds, 3),
                    "best_score": round(matched.best_score, 4),
                    "search_start_seconds": round(matched.search_start_seconds, 3),
                    "search_end_seconds": round(matched.search_end_seconds, 3),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    payload = dict(mapping)
    payload["version"] = "0.3-audio-refined"
    payload["clips"] = results
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def discover_part_videos(scratch_root: Path) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    for part_dir in sorted(path for path in scratch_root.glob("ghost-yotei-part*") if path.is_dir()):
        candidates = sorted(path for path in part_dir.glob("*.mp4") if "dialogue-cut" in path.name.lower())
        if not candidates:
            continue
        outputs[part_dir.name] = max(
            candidates,
            key=lambda path: (
                int(".fixed.mp4" in path.name.lower()),
                int("tight" in path.name.lower()),
                int("cq30" in path.name.lower()),
                path.stat().st_size,
            ),
        )
    return outputs


def load_audio_track(path: Path, sample_rate: int) -> np.ndarray:
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "-",
    ]
    raw = subprocess.check_output(command)
    audio = np.frombuffer(raw, dtype=np.float32).copy()
    if audio.size == 0:
        raise ValueError(f"Empty audio track: {path}")
    audio -= float(audio.mean())
    std = float(audio.std())
    if std > 1e-6:
        audio /= std
    return audio


def match_clip_within_part(
    clip_name: str,
    clip_audio: np.ndarray,
    part_name: str,
    part_audio: np.ndarray,
    sample_rate: int,
    search_start: float,
    search_end: float,
) -> MatchResult:
    start_index = max(0, int(search_start * sample_rate))
    end_index = min(len(part_audio), int(search_end * sample_rate))
    window = part_audio[start_index:end_index]
    if len(window) < len(clip_audio):
        raise ValueError(f"Search window too small for {clip_name} in {part_name}")

    correlation = correlate(window, clip_audio, mode="valid", method="fft")
    clip_norm = float(np.linalg.norm(clip_audio))
    window_sq = np.convolve(window * window, np.ones(len(clip_audio), dtype=np.float32), mode="valid")
    score = correlation / (np.sqrt(window_sq) * clip_norm + 1e-6)
    best_index = int(np.argmax(score))
    best_offset = (start_index + best_index) / float(sample_rate)
    return MatchResult(
        clip_name=clip_name,
        part_name=part_name,
        best_offset_seconds=best_offset,
        best_score=float(score[best_index]),
        search_start_seconds=search_start,
        search_end_seconds=search_end,
        clip_duration_seconds=(len(clip_audio) / float(sample_rate)),
    )


if __name__ == "__main__":
    main()
