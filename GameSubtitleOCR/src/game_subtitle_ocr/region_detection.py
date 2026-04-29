from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .ffmpeg_ops import probe_video, sample_frames
from .models import OcrLine, Rect
from .ocr import PaddleOcrEngine
from .utils import ensure_dir, looks_like_subtitle, percentile, save_json


def detect_subtitle_region(
    video_path: Path,
    ocr_engine: PaddleOcrEngine,
    sample_count: int,
    output_dir: Path,
    ffmpeg_bin: str | None = None,
    min_confidence: float = 0.35,
    language: str = "ch",
) -> dict[str, Any]:
    metadata = probe_video(video_path)
    sample_dir = ensure_dir(output_dir / "sample_frames")
    frames = sample_frames(video_path, count=sample_count, ffmpeg_bin=ffmpeg_bin, output_dir=sample_dir)

    boxes: list[Rect] = []
    frame_summaries: list[dict[str, Any]] = []
    width = int(metadata["width"])
    height = int(metadata["height"])

    debug_dir = ensure_dir(output_dir / "region_debug")
    for frame in frames:
        lines = ocr_engine.recognize(frame.image)
        candidates = _filter_candidate_lines(
            lines,
            width=width,
            height=height,
            min_confidence=min_confidence,
            language=language,
        )
        boxes.extend(line.box for line in candidates)
        frame_summaries.append(
            {
                "frame_index": frame.index,
                "timestamp_seconds": round(frame.timestamp_seconds, 3),
                "candidate_count": len(candidates),
                "candidates": [line.to_dict() for line in candidates[:6]],
            }
        )
        if frame.image_path is not None:
            _save_debug_image(
                image=frame.image,
                all_lines=lines,
                candidates=candidates,
                output_path=debug_dir / f"region_{frame.index:03d}.png",
            )

    recommended_crop = _recommend_crop(boxes, width=width, height=height)
    report = {
        "video_path": str(video_path),
        "video_metadata": metadata,
        "sample_count": sample_count,
        "detected_box_count": len(boxes),
        "fallback_used": len(boxes) == 0,
        "recommended_crop": recommended_crop.to_dict(),
        "frames": frame_summaries,
    }
    save_json(output_dir / "region_report.json", report)
    return report


def _filter_candidate_lines(
    lines: list[OcrLine],
    width: int,
    height: int,
    min_confidence: float,
    language: str,
) -> list[OcrLine]:
    candidates: list[OcrLine] = []
    for line in lines:
        if line.confidence < min_confidence:
            continue
        if not looks_like_subtitle(line.text, language=language):
            continue
        if line.box.center_y < height * 0.45:
            continue
        if line.box.height > height * 0.16:
            continue
        if line.box.width < width * 0.08 and len(line.text) < 4:
            continue
        candidates.append(line)
    return candidates


def _recommend_crop(boxes: list[Rect], width: int, height: int) -> Rect:
    if not boxes:
        return Rect(
            x=int(width * 0.10),
            y=int(height * 0.73),
            width=int(width * 0.80),
            height=int(height * 0.18),
        ).clamp(width, height)

    left = int(percentile([box.x for box in boxes], 0.15))
    top = int(percentile([box.y for box in boxes], 0.10))
    right = int(percentile([box.right for box in boxes], 0.90))
    bottom = int(percentile([box.bottom for box in boxes], 0.90))

    margin_x = max(16, int(width * 0.02))
    margin_y = max(12, int(height * 0.015))
    crop = Rect(
        x=max(0, left - margin_x),
        y=max(0, top - margin_y),
        width=min(width, right + margin_x) - max(0, left - margin_x),
        height=min(height, bottom + margin_y) - max(0, top - margin_y),
    )

    min_height = max(60, int(height * 0.09))
    if crop.height < min_height:
        extra = min_height - crop.height
        crop = Rect(x=crop.x, y=max(0, crop.y - (extra // 2)), width=crop.width, height=crop.height + extra)
    return crop.clamp(width, height)


def _save_debug_image(
    image: np.ndarray,
    all_lines: list[OcrLine],
    candidates: list[OcrLine],
    output_path: Path,
) -> None:
    canvas = image.copy()
    for line in all_lines:
        cv2.rectangle(
            canvas,
            (line.box.x, line.box.y),
            (line.box.right, line.box.bottom),
            (255, 160, 0),
            1,
        )
    for line in candidates:
        cv2.rectangle(
            canvas,
            (line.box.x, line.box.y),
            (line.box.right, line.box.bottom),
            (0, 255, 0),
            2,
        )
    cv2.imwrite(str(output_path), canvas)
