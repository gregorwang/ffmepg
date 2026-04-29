from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterator

import ffmpeg
import numpy as np

from .models import Rect, SampledFrame


def resolve_ffmpeg_binary(ffmpeg_bin: str | None) -> str:
    candidates = [ffmpeg_bin] if ffmpeg_bin else ["ffmpeg"]
    repo_candidate = Path(__file__).resolve().parents[3] / "tools" / "ffmpeg" / "ffmpeg.exe"
    if repo_candidate.exists():
        candidates.append(str(repo_candidate))

    for candidate in candidates:
        if not candidate:
            continue
        if Path(candidate).exists():
            return str(Path(candidate))
        found = shutil.which(candidate)
        if found:
            return found

    raise FileNotFoundError("ffmpeg.exe not found. Add it to PATH or pass --ffmpeg-bin.")


def probe_video(video_path: Path) -> dict[str, float | int | str]:
    probe_data = ffmpeg.probe(str(video_path))
    video_stream = next(stream for stream in probe_data["streams"] if stream.get("codec_type") == "video")
    duration = float(probe_data["format"].get("duration") or video_stream.get("duration") or 0.0)
    width = int(video_stream["width"])
    height = int(video_stream["height"])
    avg_frame_rate = _parse_fraction(video_stream.get("avg_frame_rate", "0/1"))
    return {
        "width": width,
        "height": height,
        "duration": duration,
        "avg_frame_rate": avg_frame_rate,
        "codec_name": video_stream.get("codec_name", ""),
    }


def build_sample_timestamps(duration: float, count: int) -> list[float]:
    if duration <= 0:
        return [0.0]
    if count <= 1:
        return [max(0.0, duration * 0.5)]
    start = duration * 0.10
    end = duration * 0.90
    interval = (end - start) / (count - 1)
    return [max(0.0, start + (interval * index)) for index in range(count)]


def sample_frames(
    video_path: Path,
    count: int,
    ffmpeg_bin: str | None = None,
    output_dir: Path | None = None,
) -> list[SampledFrame]:
    metadata = probe_video(video_path)
    width = int(metadata["width"])
    height = int(metadata["height"])
    timestamps = build_sample_timestamps(float(metadata["duration"]), count)

    frames: list[SampledFrame] = []
    for index, timestamp in enumerate(timestamps):
        frame = extract_frame_at_timestamp(
            video_path=video_path,
            timestamp_seconds=timestamp,
            width=width,
            height=height,
            ffmpeg_bin=ffmpeg_bin,
        )
        frame_path: Path | None = None
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            frame_path = output_dir / f"sample_{index:03d}_{timestamp:.3f}.png"
            _save_png(frame_path, frame)
        frames.append(
            SampledFrame(
                index=index,
                timestamp_seconds=timestamp,
                image_path=frame_path,
                image=frame,
            )
        )
    return frames


def extract_frame_at_timestamp(
    video_path: Path,
    timestamp_seconds: float,
    width: int,
    height: int,
    ffmpeg_bin: str | None = None,
) -> np.ndarray:
    ffmpeg_path = resolve_ffmpeg_binary(ffmpeg_bin)
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{timestamp_seconds:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "pipe:1",
    ]
    completed = subprocess.run(command, check=True, capture_output=True)
    expected_size = width * height * 3
    if len(completed.stdout) != expected_size:
        raise RuntimeError(
            f"Unexpected raw frame size at {timestamp_seconds:.3f}s: "
            f"expected {expected_size}, got {len(completed.stdout)}"
        )
    frame = np.frombuffer(completed.stdout, dtype=np.uint8).reshape((height, width, 3))
    return frame.copy()


def stream_frames(
    video_path: Path,
    fps: float,
    crop: Rect,
    ffmpeg_bin: str | None = None,
    start_time: float = 0.0,
    end_time: float | None = None,
) -> Iterator[tuple[int, float, np.ndarray]]:
    ffmpeg_path = resolve_ffmpeg_binary(ffmpeg_bin)
    filters = [f"fps={fps:.6f}", f"crop={crop.width}:{crop.height}:{crop.x}:{crop.y}"]
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_time:.3f}",
        "-i",
        str(video_path),
    ]
    if end_time is not None:
        duration = max(0.0, end_time - start_time)
        command.extend(["-t", f"{duration:.3f}"])
    command.extend(
        [
            "-vf",
            ",".join(filters),
            "-an",
            "-sn",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
    )

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdout is None:
        raise RuntimeError("Failed to capture ffmpeg stdout.")

    frame_size = crop.width * crop.height * 3
    frame_index = 0
    try:
        while True:
            buffer = process.stdout.read(frame_size)
            if not buffer:
                break
            if len(buffer) != frame_size:
                break
            image = np.frombuffer(buffer, dtype=np.uint8).reshape((crop.height, crop.width, 3)).copy()
            timestamp = start_time + (frame_index / fps)
            yield frame_index, timestamp, image
            frame_index += 1
    finally:
        process.stdout.close()
        stderr = process.stderr.read().decode("utf-8", errors="ignore") if process.stderr else ""
        process.wait(timeout=10)
        if process.returncode not in (0, None):
            raise RuntimeError(f"ffmpeg stream failed with code {process.returncode}: {stderr}")


def _parse_fraction(raw: str) -> float:
    if not raw or raw == "0/0":
        return 0.0
    left, right = raw.split("/", maxsplit=1)
    denominator = float(right)
    if denominator == 0:
        return 0.0
    return float(left) / denominator


def _save_png(path: Path, image: np.ndarray) -> None:
    import cv2

    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Failed to save image: {path}")
