from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import (
    DEFAULT_EXTRACTION_FPS,
    DEFAULT_MAX_GAP_FRAMES,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_DURATION_SECONDS,
    DEFAULT_REGION_SAMPLE_COUNT,
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TUNE_SAMPLE_COUNT,
)
from .postprocess import cues_to_srt
from .models import Rect
from .subtitle_tools import (
    align_english_transcript_to_chinese,
    clean_subtitle_cues,
    load_cues_from_path,
    prepare_audit_dataset,
    score_audit_dataset,
    write_cues_json,
)
from .utils import ensure_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="game-subtitle-ocr")
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect = subparsers.add_parser("detect-region", help="Sample frames and recommend subtitle crop coordinates.")
    _add_shared_inputs(detect)
    detect.add_argument("--sample-count", type=int, default=DEFAULT_REGION_SAMPLE_COUNT)
    detect.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)

    tune = subparsers.add_parser("tune", help="Compare preprocessing profiles and output OCR report.")
    _add_shared_inputs(tune)
    tune.add_argument("--crop", type=str)
    tune.add_argument("--crop-json", type=Path)
    tune.add_argument("--sample-count", type=int, default=DEFAULT_TUNE_SAMPLE_COUNT)
    tune.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)

    extract = subparsers.add_parser("extract", help="Extract hard subtitles into SRT.")
    _add_shared_inputs(extract)
    extract.add_argument("--crop", type=str)
    extract.add_argument("--crop-json", type=Path)
    extract.add_argument("--profile-json", type=Path)
    extract.add_argument("--profile-name", type=str)
    extract.add_argument("--output-srt", type=Path)
    extract.add_argument("--fps", type=float, default=DEFAULT_EXTRACTION_FPS)
    extract.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    extract.add_argument("--similarity-threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    extract.add_argument("--max-gap-frames", type=int, default=DEFAULT_MAX_GAP_FRAMES)
    extract.add_argument("--min-duration", type=float, default=DEFAULT_MIN_DURATION_SECONDS)

    run = subparsers.add_parser("run", help="Run region detection, tuning and extraction end-to-end.")
    _add_shared_inputs(run)
    run.add_argument("--sample-count", type=int, default=DEFAULT_REGION_SAMPLE_COUNT)
    run.add_argument("--tune-sample-count", type=int, default=DEFAULT_TUNE_SAMPLE_COUNT)
    run.add_argument("--output-srt", type=Path)
    run.add_argument("--fps", type=float, default=DEFAULT_EXTRACTION_FPS)
    run.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    run.add_argument("--similarity-threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    run.add_argument("--max-gap-frames", type=int, default=DEFAULT_MAX_GAP_FRAMES)
    run.add_argument("--min-duration", type=float, default=DEFAULT_MIN_DURATION_SECONDS)

    refine = subparsers.add_parser("refine-srt", help="Clean an OCR SRT and export cleaned JSON/SRT.")
    refine_inputs = refine.add_mutually_exclusive_group(required=True)
    refine_inputs.add_argument("--input-srt", type=Path)
    refine_inputs.add_argument("--input-json", type=Path)
    refine.add_argument("--output-json", type=Path, required=True)
    refine.add_argument("--output-srt", type=Path)
    refine.add_argument("--similarity-threshold", type=float, default=0.72)
    refine.add_argument("--max-merge-gap", type=float, default=0.6)
    refine.add_argument("--min-text-length", type=int, default=2)
    refine.add_argument("--min-confidence", type=float)
    refine.add_argument("--language", choices=["ch", "en"], default="ch")

    prepare_audit = subparsers.add_parser("prepare-audit", help="Sample subtitle cues into an audit pack.")
    prepare_audit_inputs = prepare_audit.add_mutually_exclusive_group(required=True)
    prepare_audit_inputs.add_argument("--input-srt", type=Path)
    prepare_audit_inputs.add_argument("--input-json", type=Path)
    prepare_audit.add_argument("--output-json", type=Path, required=True)
    prepare_audit.add_argument("--sample-count", type=int, default=50)
    prepare_audit.add_argument("--source-video", type=Path)
    prepare_audit.add_argument("--crop", type=str)
    prepare_audit.add_argument("--ffmpeg-bin", type=str)

    score_audit = subparsers.add_parser("score-audit", help="Score an annotated audit pack.")
    score_audit.add_argument("--input-json", type=Path, required=True)
    score_audit.add_argument("--output-json", type=Path)
    score_audit.add_argument("--pass-threshold", type=float, default=0.90)

    align = subparsers.add_parser("align-bilingual", help="Align English transcript JSON with Chinese subtitle cues.")
    align.add_argument("--english-json", type=Path, required=True)
    align.add_argument("--chinese-json", type=Path)
    align.add_argument("--chinese-srt", type=Path)
    align.add_argument("--output-json", type=Path, required=True)
    align.add_argument("--max-offset", type=float, default=1.5)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if hasattr(args, "output_dir"):
        args.output_dir = ensure_dir(args.output_dir)

    if args.command == "run":
        from .pipeline import run_full_pipeline

        report = run_full_pipeline(
            video_path=args.input,
            output_dir=args.output_dir,
            device=args.device,
            model_profile=args.model_profile,
            language=args.language,
            sample_count=args.sample_count,
            tune_sample_count=args.tune_sample_count,
            fps=args.fps,
            min_confidence=args.min_confidence,
            similarity_threshold=args.similarity_threshold,
            max_gap_frames=args.max_gap_frames,
            min_duration_seconds=args.min_duration,
            ffmpeg_bin=args.ffmpeg_bin,
            output_srt=args.output_srt,
        )
        print(json.dumps(report["extraction_report"], ensure_ascii=False, indent=2))
        return

    if args.command == "refine-srt":
        input_path = args.input_json or args.input_srt
        if input_path is None:
            raise ValueError("Pass --input-json or --input-srt.")
        cues = load_cues_from_path(input_path)
        cleaned = clean_subtitle_cues(
            cues,
            similarity_threshold=args.similarity_threshold,
            max_merge_gap_seconds=args.max_merge_gap,
            min_text_length=args.min_text_length,
            min_confidence=args.min_confidence,
            language=args.language,
        )
        write_cues_json(
            output_path=args.output_json,
            cues=cleaned,
            source_path=input_path,
            language="en" if args.language == "en" else "zh-Hans",
            metadata={
                "kind": "cleaned-ocr-subtitles",
                "input_kind": input_path.suffix.lower().lstrip("."),
                "language": args.language,
                "similarity_threshold": args.similarity_threshold,
                "max_merge_gap_seconds": args.max_merge_gap,
                "min_text_length": args.min_text_length,
                "min_confidence": args.min_confidence,
            },
        )
        if args.output_srt is not None:
            args.output_srt.write_text(cues_to_srt(cleaned), encoding="utf-8")
        print(
            json.dumps(
                {
                    "input": str(input_path),
                    "output_json": str(args.output_json),
                    "output_srt": str(args.output_srt) if args.output_srt is not None else None,
                    "cue_count": len(cleaned),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "prepare-audit":
        input_path = args.input_json or args.input_srt
        if input_path is None:
            raise ValueError("Pass --input-json or --input-srt.")
        crop = Rect.parse(args.crop) if args.crop else None
        payload = prepare_audit_dataset(
            cues_path=input_path,
            output_path=args.output_json,
            sample_count=args.sample_count,
            source_video_path=args.source_video,
            crop=crop,
            ffmpeg_bin=args.ffmpeg_bin,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "score-audit":
        report = score_audit_dataset(
            audit_path=args.input_json,
            output_path=args.output_json,
            pass_threshold=args.pass_threshold,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if args.command == "align-bilingual":
        chinese_path = args.chinese_json or args.chinese_srt
        if chinese_path is None:
            raise ValueError("Pass --chinese-json or --chinese-srt.")
        align_english_transcript_to_chinese(
            english_json_path=args.english_json,
            chinese_cues_path=chinese_path,
            output_path=args.output_json,
            max_offset_seconds=args.max_offset,
        )
        print(
            json.dumps(
                {
                    "english_json": str(args.english_json),
                    "chinese_source": str(chinese_path),
                    "output_json": str(args.output_json),
                    "max_offset_seconds": args.max_offset,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    from .ocr import PaddleOcrEngine

    ocr_engine = PaddleOcrEngine(device=args.device, model_profile=args.model_profile, language=args.language)
    try:
        if args.command == "detect-region":
            from .region_detection import detect_subtitle_region

            report = detect_subtitle_region(
                video_path=args.input,
                ocr_engine=ocr_engine,
                sample_count=args.sample_count,
                output_dir=args.output_dir,
                ffmpeg_bin=args.ffmpeg_bin,
                min_confidence=args.min_confidence,
                language=args.language,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return

        if args.command == "tune":
            from .pipeline import load_crop_argument
            from .tuning import run_parameter_tuning

            crop = load_crop_argument(args.crop, args.crop_json)
            report = run_parameter_tuning(
                video_path=args.input,
                crop=crop,
                ocr_engine=ocr_engine,
                sample_count=args.sample_count,
                output_dir=args.output_dir,
                ffmpeg_bin=args.ffmpeg_bin,
                min_confidence=args.min_confidence,
                language=args.language,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return

        if args.command == "extract":
            from .pipeline import extract_subtitles, load_crop_argument, load_profile_argument

            crop = load_crop_argument(args.crop, args.crop_json)
            profile = load_profile_argument(args.profile_json, args.profile_name)
            report = extract_subtitles(
                video_path=args.input,
                crop=crop,
                profile=profile,
                ocr_engine=ocr_engine,
                output_dir=args.output_dir,
                output_srt=args.output_srt,
                fps=args.fps,
                min_confidence=args.min_confidence,
                similarity_threshold=args.similarity_threshold,
                max_gap_frames=args.max_gap_frames,
                min_duration_seconds=args.min_duration,
                ffmpeg_bin=args.ffmpeg_bin,
                language=args.language,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
    finally:
        ocr_engine.close()


def _add_shared_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg-bin", type=str)
    parser.add_argument("--device", choices=["gpu", "cpu"], default="gpu")
    parser.add_argument("--model-profile", choices=["mobile", "server"], default="mobile")
    parser.add_argument("--language", choices=["ch", "en"], default="ch")


if __name__ == "__main__":
    main()
