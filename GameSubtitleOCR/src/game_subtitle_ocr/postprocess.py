from __future__ import annotations

from .models import FrameSubtitleResult, SubtitleCue
from .utils import normalize_text, seconds_to_srt_time, text_similarity


def merge_frame_results(
    frames: list[FrameSubtitleResult],
    frame_interval_seconds: float,
    similarity_threshold: float,
    max_gap_frames: int,
    min_duration_seconds: float,
) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []
    active: dict[str, float | str] | None = None
    blank_run = 0

    for frame in frames:
        text = normalize_text(frame.text)
        if not text:
            if active is None:
                continue
            blank_run += 1
            if blank_run <= max_gap_frames:
                continue
            cues.append(_finalize_active(active, len(cues) + 1, frame_interval_seconds, min_duration_seconds))
            active = None
            blank_run = 0
            continue

        blank_run = 0
        if active is None:
            active = {
                "text": text,
                "start": frame.timestamp_seconds,
                "last_text": frame.timestamp_seconds,
                "confidence_sum": frame.confidence,
                "confidence_count": 1.0,
            }
            continue

        similarity = text_similarity(str(active["text"]), text)
        if similarity >= similarity_threshold:
            active["last_text"] = frame.timestamp_seconds
            active["confidence_sum"] = float(active["confidence_sum"]) + frame.confidence
            active["confidence_count"] = float(active["confidence_count"]) + 1.0
            if len(text) > len(str(active["text"])) and similarity >= 0.92:
                active["text"] = text
            continue

        cues.append(_finalize_active(active, len(cues) + 1, frame_interval_seconds, min_duration_seconds))
        active = {
            "text": text,
            "start": frame.timestamp_seconds,
            "last_text": frame.timestamp_seconds,
            "confidence_sum": frame.confidence,
            "confidence_count": 1.0,
        }

    if active is not None:
        cues.append(_finalize_active(active, len(cues) + 1, frame_interval_seconds, min_duration_seconds))

    return _merge_adjacent_cues(cues, similarity_threshold=similarity_threshold, frame_interval_seconds=frame_interval_seconds)


def cues_to_srt(cues: list[SubtitleCue]) -> str:
    blocks: list[str] = []
    for cue in cues:
        blocks.append(
            "\n".join(
                [
                    str(cue.index),
                    f"{seconds_to_srt_time(cue.start_seconds)} --> {seconds_to_srt_time(cue.end_seconds)}",
                    cue.text,
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _finalize_active(
    active: dict[str, float | str],
    index: int,
    frame_interval_seconds: float,
    min_duration_seconds: float,
) -> SubtitleCue:
    start = float(active["start"])
    last_text = float(active["last_text"])
    end = max(start + min_duration_seconds, last_text + frame_interval_seconds)
    confidence = float(active["confidence_sum"]) / max(1.0, float(active["confidence_count"]))
    return SubtitleCue(
        index=index,
        start_seconds=start,
        end_seconds=end,
        text=str(active["text"]),
        confidence=confidence,
    )


def _merge_adjacent_cues(
    cues: list[SubtitleCue],
    similarity_threshold: float,
    frame_interval_seconds: float,
) -> list[SubtitleCue]:
    if not cues:
        return []
    merged: list[SubtitleCue] = [cues[0]]
    for cue in cues[1:]:
        previous = merged[-1]
        gap = cue.start_seconds - previous.end_seconds
        if gap <= frame_interval_seconds and text_similarity(previous.text, cue.text) >= similarity_threshold:
            merged[-1] = SubtitleCue(
                index=previous.index,
                start_seconds=previous.start_seconds,
                end_seconds=max(previous.end_seconds, cue.end_seconds),
                text=previous.text if len(previous.text) >= len(cue.text) else cue.text,
                confidence=max(previous.confidence, cue.confidence),
            )
            continue
        merged.append(
            SubtitleCue(
                index=len(merged) + 1,
                start_seconds=cue.start_seconds,
                end_seconds=cue.end_seconds,
                text=cue.text,
                confidence=cue.confidence,
            )
        )
    return merged
