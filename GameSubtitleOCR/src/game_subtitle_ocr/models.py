from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center_y(self) -> float:
        return self.y + (self.height / 2.0)

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    def clamp(self, max_width: int, max_height: int) -> "Rect":
        x = min(max(self.x, 0), max_width - 1)
        y = min(max(self.y, 0), max_height - 1)
        right = min(max(self.right, x + 1), max_width)
        bottom = min(max(self.bottom, y + 1), max_height)
        return Rect(x=x, y=y, width=right - x, height=bottom - y)

    @classmethod
    def from_points(cls, points: list[list[float]] | list[tuple[float, float]]) -> "Rect":
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        left = int(min(xs))
        top = int(min(ys))
        right = int(max(xs))
        bottom = int(max(ys))
        return cls(x=left, y=top, width=max(1, right - left), height=max(1, bottom - top))

    @classmethod
    def parse(cls, raw: str) -> "Rect":
        pieces = [int(part.strip()) for part in raw.split(",")]
        if len(pieces) != 4:
            raise ValueError("Crop must use x,y,width,height format.")
        return cls(x=pieces[0], y=pieces[1], width=pieces[2], height=pieces[3])


@dataclass(slots=True)
class SampledFrame:
    index: int
    timestamp_seconds: float
    image_path: Path | None
    image: Any


@dataclass(slots=True)
class OcrLine:
    text: str
    confidence: float
    box: Rect

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "box": self.box.to_dict(),
        }


@dataclass(slots=True)
class FrameSubtitleResult:
    frame_index: int
    timestamp_seconds: float
    text: str
    confidence: float
    line_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp_seconds": round(self.timestamp_seconds, 3),
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "line_count": self.line_count,
        }


@dataclass(slots=True)
class PreprocessProfile:
    name: str
    scale: float = 1.0
    grayscale: bool = True
    denoise_kernel: int = 0
    threshold_mode: str = "none"
    invert: bool = False
    sharpen: bool = False
    morphology_close: int = 0
    contrast: float = 1.0
    brightness: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PreprocessProfile":
        return cls(**payload)


@dataclass(slots=True)
class ProfileScore:
    profile: PreprocessProfile
    score: float
    detected_frames: int
    sample_count: int
    average_confidence: float
    average_text_length: float
    average_chinese_ratio: float
    sample_outputs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "score": round(self.score, 4),
            "detected_frames": self.detected_frames,
            "sample_count": self.sample_count,
            "average_confidence": round(self.average_confidence, 4),
            "average_text_length": round(self.average_text_length, 4),
            "average_chinese_ratio": round(self.average_chinese_ratio, 4),
            "sample_outputs": self.sample_outputs,
        }


@dataclass(slots=True)
class SubtitleCue:
    index: int
    start_seconds: float
    end_seconds: float
    text: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
            "text": self.text,
            "confidence": round(self.confidence, 4),
        }
