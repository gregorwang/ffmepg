from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any

from .config import build_default_profiles
from .ffmpeg_ops import sample_frames
from .models import OcrLine, PreprocessProfile, ProfileScore, Rect, SampledFrame
from .ocr import PaddleOcrEngine
from .preprocess import apply_preprocess
from .utils import chinese_ratio, ensure_dir, latin_ratio, looks_like_subtitle, save_json, save_text


def run_parameter_tuning(
    video_path: Path,
    crop: Rect,
    ocr_engine: PaddleOcrEngine,
    sample_count: int,
    output_dir: Path,
    ffmpeg_bin: str | None = None,
    min_confidence: float = 0.35,
    profiles: list[PreprocessProfile] | None = None,
    language: str = "ch",
) -> dict[str, Any]:
    frames = sample_frames(
        video_path=video_path,
        count=sample_count,
        ffmpeg_bin=ffmpeg_bin,
        output_dir=ensure_dir(output_dir / "tuning_samples"),
    )
    scores = evaluate_profiles(
        frames,
        crop,
        ocr_engine,
        min_confidence=min_confidence,
        profiles=profiles,
        language=language,
    )
    best = max(scores, key=lambda item: item.score)

    report = {
        "video_path": str(video_path),
        "crop": crop.to_dict(),
        "sample_count": sample_count,
        "best_profile": best.profile.to_dict(),
        "profiles": [item.to_dict() for item in scores],
    }
    save_json(output_dir / "tuning_report.json", report)
    save_text(output_dir / "tuning_report.md", render_markdown_report(scores))
    return report


def evaluate_profiles(
    frames: list[SampledFrame],
    crop: Rect,
    ocr_engine: PaddleOcrEngine,
    min_confidence: float,
    profiles: list[PreprocessProfile] | None = None,
    language: str = "ch",
) -> list[ProfileScore]:
    profiles = profiles or build_default_profiles()
    results: list[ProfileScore] = []
    for profile in profiles:
        result = _score_profile(
            frames=frames,
            crop=crop,
            ocr_engine=ocr_engine,
            profile=profile,
            min_confidence=min_confidence,
            language=language,
        )
        results.append(result)
    return sorted(results, key=lambda item: item.score, reverse=True)


def _score_profile(
    frames: list[SampledFrame],
    crop: Rect,
    ocr_engine: PaddleOcrEngine,
    profile: PreprocessProfile,
    min_confidence: float,
    language: str,
) -> ProfileScore:
    non_empty_texts: list[str] = []
    confidences: list[float] = []
    lengths: list[int] = []
    language_scores: list[float] = []
    samples: list[dict[str, Any]] = []

    for frame in frames:
        prepared = apply_preprocess(frame.image, profile=profile, crop=crop)
        lines = ocr_engine.recognize(prepared)
        selected = select_subtitle_lines(lines, min_confidence=min_confidence, language=language)
        text, confidence = join_lines(selected)
        if text:
            non_empty_texts.append(text)
            confidences.append(confidence)
            lengths.append(len(text.replace("\n", "")))
            language_scores.append(chinese_ratio(text) if language == "ch" else latin_ratio(text))
        if len(samples) < 6:
            samples.append(
                {
                    "frame_index": frame.index,
                    "timestamp_seconds": round(frame.timestamp_seconds, 3),
                    "text": text,
                    "confidence": round(confidence, 4),
                }
            )

    coverage = len(non_empty_texts) / max(1, len(frames))
    average_confidence = mean(confidences) if confidences else 0.0
    average_length = mean(lengths) if lengths else 0.0
    average_chinese_ratio = mean(language_scores) if language_scores else 0.0
    length_score = min(1.0, average_length / 14.0)
    score = (coverage * 0.40) + (average_confidence * 0.30) + (average_chinese_ratio * 0.20) + (length_score * 0.10)

    return ProfileScore(
        profile=profile,
        score=score,
        detected_frames=len(non_empty_texts),
        sample_count=len(frames),
        average_confidence=average_confidence,
        average_text_length=average_length,
        average_chinese_ratio=average_chinese_ratio,
        sample_outputs=samples,
    )


def select_subtitle_lines(lines: list[OcrLine], min_confidence: float, language: str = "ch") -> list[OcrLine]:
    selected = [
        line
        for line in lines
        if line.confidence >= min_confidence and looks_like_subtitle(line.text, language=language)
    ]
    return sorted(selected, key=lambda item: (item.box.y, item.box.x))


def join_lines(lines: list[OcrLine]) -> tuple[str, float]:
    if not lines:
        return "", 0.0
    text = "\n".join(line.text.strip() for line in lines if line.text.strip())
    confidence = sum(line.confidence for line in lines) / len(lines)
    return text.strip(), confidence


def render_markdown_report(scores: list[ProfileScore]) -> str:
    lines = [
        "# OCR 参数调优报告",
        "",
        "| 排名 | Profile | Score | Detected / Sample | Avg Conf | Avg Len | Avg Chinese Ratio |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for index, score in enumerate(scores, start=1):
        lines.append(
            "| "
            f"{index} | {score.profile.name} | {score.score:.4f} | "
            f"{score.detected_frames}/{score.sample_count} | {score.average_confidence:.4f} | "
            f"{score.average_text_length:.2f} | {score.average_chinese_ratio:.4f} |"
        )

    lines.append("")
    lines.append("## Top 3 示例")
    lines.append("")
    for score in scores[:3]:
        lines.append(f"### {score.profile.name}")
        for sample in score.sample_outputs:
            lines.append(
                f"- t={sample['timestamp_seconds']:.3f}s conf={sample['confidence']:.4f} text={sample['text'] or '[empty]'}"
            )
        lines.append("")

    return "\n".join(lines)
