from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_BETWEEN_RE = re.compile(r"between\(t,([0-9]+(?:\.[0-9]+)?),([0-9]+(?:\.[0-9]+)?)\)")
_VIDEO_SELECT_RE = re.compile(r"\[0:v:0\]select='([^']+)'")


@dataclass(slots=True)
class FilterInterval:
    original_start: float
    original_end: float
    cut_start: float
    cut_end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.original_end - self.original_start)


def parse_filter_intervals(text: str) -> list[FilterInterval]:
    match = _VIDEO_SELECT_RE.search(text)
    source = match.group(1) if match else text
    raw = [(float(start), float(end)) for start, end in _BETWEEN_RE.findall(source)]
    intervals: list[FilterInterval] = []
    cursor = 0.0
    for original_start, original_end in raw:
        duration = max(0.0, original_end - original_start)
        intervals.append(
            FilterInterval(
                original_start=original_start,
                original_end=original_end,
                cut_start=cursor,
                cut_end=cursor + duration,
            )
        )
        cursor += duration
    return intervals


def load_filter_intervals(path: Path) -> list[FilterInterval]:
    return parse_filter_intervals(path.read_text(encoding="utf-8-sig"))


def map_original_time_to_cut(time_seconds: float, intervals: list[FilterInterval]) -> float | None:
    for interval in intervals:
        if interval.original_start <= time_seconds <= interval.original_end:
            return interval.cut_start + (time_seconds - interval.original_start)
    return None


def map_original_range_to_cut_ranges(
    original_start: float,
    original_end: float,
    intervals: list[FilterInterval],
) -> list[tuple[float, float]]:
    if original_end < original_start:
        original_start, original_end = original_end, original_start

    outputs: list[tuple[float, float]] = []
    for interval in intervals:
        overlap_start = max(original_start, interval.original_start)
        overlap_end = min(original_end, interval.original_end)
        if overlap_end <= overlap_start:
            continue
        cut_start = interval.cut_start + (overlap_start - interval.original_start)
        cut_end = interval.cut_start + (overlap_end - interval.original_start)
        outputs.append((round(cut_start, 3), round(cut_end, 3)))
    return outputs
