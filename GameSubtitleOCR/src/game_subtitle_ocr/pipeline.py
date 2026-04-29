from __future__ import annotations

from pathlib import Path
from typing import Any

from tqdm import tqdm

from .config import (
    build_default_profiles,
    DEFAULT_EXTRACTION_FPS,
    DEFAULT_MAX_GAP_FRAMES,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_DURATION_SECONDS,
    DEFAULT_REGION_SAMPLE_COUNT,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TUNE_SAMPLE_COUNT,
)
from .ffmpeg_ops import probe_video, stream_frames
from .models import FrameSubtitleResult, PreprocessProfile, Rect
from .ocr import PaddleOcrEngine
from .postprocess import cues_to_srt, merge_frame_results
from .preprocess import apply_preprocess
from .region_detection import detect_subtitle_region
from .subtitle_tools import write_cues_json
from .tuning import join_lines, run_parameter_tuning, select_subtitle_lines
from .utils import ensure_dir, load_json, safe_output_stem, save_json, save_text


def run_full_pipeline(
    video_path: Path,
    output_dir: Path,
    device: str = "gpu",
    model_profile: str = "mobile",
    sample_count: int = DEFAULT_REGION_SAMPLE_COUNT,
    tune_sample_count: int = DEFAULT_TUNE_SAMPLE_COUNT,
    fps: float = DEFAULT_EXTRACTION_FPS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_gap_frames: int = DEFAULT_MAX_GAP_FRAMES,
    min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS,
    ffmpeg_bin: str | None = None,
    output_srt: Path | None = None,
    language: str = "ch",
) -> dict[str, Any]:
    output_dir = ensure_dir(output_dir)
    ocr_engine = PaddleOcrEngine(device=device, model_profile=model_profile, language=language)
    try:
        region_report = detect_subtitle_region(
            video_path=video_path,
            ocr_engine=ocr_engine,
            sample_count=sample_count,
            output_dir=output_dir,
            ffmpeg_bin=ffmpeg_bin,
            min_confidence=min_confidence,
            language=language,
        )
        crop = Rect(**region_report["recommended_crop"])
        tuning_report = run_parameter_tuning(
            video_path=video_path,
            crop=crop,
            ocr_engine=ocr_engine,
            sample_count=tune_sample_count,
            output_dir=output_dir,
            ffmpeg_bin=ffmpeg_bin,
            min_confidence=min_confidence,
            language=language,
        )
        profile = PreprocessProfile.from_dict(tuning_report["best_profile"])
        extraction_report = extract_subtitles(
            video_path=video_path,
            crop=crop,
            profile=profile,
            ocr_engine=ocr_engine,
            output_dir=output_dir,
            output_srt=output_srt,
            fps=fps,
            min_confidence=min_confidence,
            similarity_threshold=similarity_threshold,
            max_gap_frames=max_gap_frames,
            min_duration_seconds=min_duration_seconds,
            ffmpeg_bin=ffmpeg_bin,
            language=language,
        )
        return {
            "region_report": region_report,
            "tuning_report": tuning_report,
            "extraction_report": extraction_report,
        }
    finally:
        ocr_engine.close()


def extract_subtitles(
    video_path: Path,
    crop: Rect,
    profile: PreprocessProfile,
    ocr_engine: PaddleOcrEngine,
    output_dir: Path,
    output_srt: Path | None = None,
    fps: float = DEFAULT_EXTRACTION_FPS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_gap_frames: int = DEFAULT_MAX_GAP_FRAMES,
    min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS,
    ffmpeg_bin: str | None = None,
    language: str = "ch",
) -> dict[str, Any]:
    output_dir = ensure_dir(output_dir)
    metadata = probe_video(video_path)
    duration = float(metadata["duration"])
    suffix = "english" if language == "en" else "chinese"
    output_srt = output_srt or (output_dir / f"{safe_output_stem(video_path)}_{suffix}.srt")
    output_json = output_srt.with_suffix(".json")

    frame_results: list[FrameSubtitleResult] = []
    estimated_frames = max(1, int(duration * fps))
    progress = tqdm(total=estimated_frames, desc="OCR extracting", unit="frame")
    try:
        for frame_index, timestamp_seconds, image in stream_frames(
            video_path=video_path,
            fps=fps,
            crop=crop,
            ffmpeg_bin=ffmpeg_bin,
        ):
            prepared = apply_preprocess(image=image, profile=profile)
            lines = ocr_engine.recognize(prepared)
            selected = select_subtitle_lines(lines, min_confidence=min_confidence, language=language)
            text, confidence = join_lines(selected)
            frame_results.append(
                FrameSubtitleResult(
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                    text=text,
                    confidence=confidence,
                    line_count=len(selected),
                )
            )
            progress.update(1)
    finally:
        progress.close()

    frame_interval_seconds = 1.0 / fps
    cues = merge_frame_results(
        frames=frame_results,
        frame_interval_seconds=frame_interval_seconds,
        similarity_threshold=similarity_threshold,
        max_gap_frames=max_gap_frames,
        min_duration_seconds=min_duration_seconds,
    )
    srt_text = cues_to_srt(cues)
    save_text(output_srt, srt_text)
    write_cues_json(
        output_path=output_json,
        cues=cues,
        source_path=video_path,
        metadata={
            "crop": crop.to_dict(),
            "profile": profile.to_dict(),
            "language": language,
            "fps": fps,
            "min_confidence": min_confidence,
            "similarity_threshold": similarity_threshold,
            "max_gap_frames": max_gap_frames,
            "min_duration_seconds": min_duration_seconds,
        },
        language="en" if language == "en" else "zh-Hans",
    )

    report = {
        "video_path": str(video_path),
        "crop": crop.to_dict(),
        "profile": profile.to_dict(),
        "language": language,
        "fps": fps,
        "frame_count": len(frame_results),
        "cue_count": len(cues),
        "output_srt": str(output_srt),
        "output_json": str(output_json),
        "sample_frame_results": [item.to_dict() for item in frame_results[:20]],
        "cues": [cue.to_dict() for cue in cues[:100]],
    }
    save_json(output_dir / "extraction_report.json", report)
    return report


def load_crop_argument(crop: str | None, crop_json: Path | None) -> Rect:
    if crop:
        return Rect.parse(crop)
    if crop_json:
        payload = load_json(crop_json)
        crop_payload = payload.get("recommended_crop") or payload.get("crop")
        if not isinstance(crop_payload, dict):
            raise ValueError(f"Unable to read crop from: {crop_json}")
        return Rect(**crop_payload)
    raise ValueError("Crop is required. Pass --crop or --crop-json.")


def load_profile_argument(profile_json: Path | None, profile_name: str | None) -> PreprocessProfile:
    if profile_name:
        for profile in build_default_profiles():
            if profile.name == profile_name:
                return profile
    if profile_json is None:
        raise ValueError("Profile is required. Pass --profile-json or --profile-name.")
    payload = load_json(profile_json)
    if profile_name and "profiles" in payload:
        for item in payload["profiles"]:
            profile = item.get("profile", {})
            if profile.get("name") == profile_name:
                return PreprocessProfile.from_dict(profile)
    if "best_profile" in payload:
        return PreprocessProfile.from_dict(payload["best_profile"])
    if "profile" in payload:
        return PreprocessProfile.from_dict(payload["profile"])
    raise ValueError(f"Unable to read profile from: {profile_json}")
