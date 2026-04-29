from __future__ import annotations

import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


_SPACE_RE = re.compile(r"\s+")
_SUBTITLE_RE = re.compile(r"[\u3400-\u9fff\uff01-\uff5e]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def normalize_text(text: str) -> str:
    normalized = text.replace("|", "丨").replace("…", "...")
    normalized = normalized.replace("，", "，").replace("。", "。")
    normalized = _SPACE_RE.sub(" ", normalized)
    return normalized.strip()


def chinese_ratio(text: str) -> float:
    stripped = normalize_text(text).replace(" ", "")
    if not stripped:
        return 0.0
    chinese_chars = sum(1 for char in stripped if is_cjk(char) or char in "，。！？：；、“”‘’（）《》【】")
    return chinese_chars / len(stripped)


def latin_ratio(text: str) -> float:
    stripped = normalize_text(text).replace(" ", "")
    if not stripped:
        return 0.0
    latin_chars = sum(1 for char in stripped if char.isascii() and (char.isalpha() or char in ".,!?;:'\"-()"))
    return latin_chars / len(stripped)


def is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x2EBEF
    )


def looks_like_subtitle(text: str, language: str = "ch") -> bool:
    cleaned = normalize_text(text)
    if len(cleaned) < 2:
        return False
    language = (language or "ch").lower()
    if language == "en":
        if not _LATIN_RE.search(cleaned):
            return False
        lowered = cleaned.lower()
        if "mkiceandfire" in lowered:
            return False
        if len(cleaned.replace(" ", "")) < 3:
            return False
        return latin_ratio(cleaned) >= 0.45

    if not _SUBTITLE_RE.search(cleaned):
        return False
    return chinese_ratio(cleaned) >= 0.45


def text_similarity(left: str, right: str) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm and not right_norm:
        return 1.0
    if not left_norm or not right_norm:
        return 0.0
    return SequenceMatcher(a=left_norm, b=right_norm).ratio()


def percentile(values: list[float], p: float) -> float:
    if not values:
        raise ValueError("Percentile requires at least one value.")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * p
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def seconds_to_srt_time(value: float) -> str:
    milliseconds = max(0, int(round(value * 1000.0)))
    hours = milliseconds // 3_600_000
    milliseconds -= hours * 3_600_000
    minutes = milliseconds // 60_000
    milliseconds -= minutes * 60_000
    seconds = milliseconds // 1000
    milliseconds -= seconds * 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def safe_output_stem(video_path: Path) -> str:
    return video_path.stem.replace(" ", "_")
