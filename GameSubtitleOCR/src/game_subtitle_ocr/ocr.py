from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .models import OcrLine, Rect


class PaddleOcrEngine:
    def __init__(self, device: str = "gpu", model_profile: str = "mobile", language: str = "ch") -> None:
        from paddleocr import PaddleOCR

        self._temp_dir = tempfile.TemporaryDirectory(prefix="game_subtitle_ocr_")
        self._engine = None
        self._predict_mode = False
        device_name = "gpu:0" if device.lower() == "gpu" else "cpu"
        language = (language or "ch").lower()

        candidate_kwargs: list[dict[str, Any]] = []
        if language == "ch" and model_profile == "mobile":
            candidate_kwargs.append(
                {
                    "device": device_name,
                    "use_doc_orientation_classify": False,
                    "use_doc_unwarping": False,
                    "use_textline_orientation": False,
                    "text_detection_model_name": "PP-OCRv5_mobile_det",
                    "text_recognition_model_name": "PP-OCRv5_mobile_rec",
                }
            )
        elif language == "ch" and model_profile == "server":
            candidate_kwargs.append(
                {
                    "device": device_name,
                    "use_doc_orientation_classify": False,
                    "use_doc_unwarping": False,
                    "use_textline_orientation": False,
                    "text_detection_model_name": "PP-OCRv5_server_det",
                    "text_recognition_model_name": "PP-OCRv5_server_rec",
                }
            )

        candidate_kwargs.extend(
            [
                {
                    "device": device_name,
                    "lang": language,
                    "use_doc_orientation_classify": False,
                    "use_doc_unwarping": False,
                    "use_textline_orientation": False,
                },
            ]
        )
        if language == "ch":
            candidate_kwargs.append(
                {
                    "lang": "ch",
                    "ocr_version": "PP-OCRv5",
                }
            )

        last_error: Exception | None = None
        for kwargs in candidate_kwargs:
            try:
                self._engine = PaddleOCR(**kwargs)
                break
            except Exception as exc:  # pragma: no cover
                last_error = exc

        if self._engine is None:
            raise RuntimeError(f"Failed to initialize PaddleOCR: {last_error}") from last_error

        self._predict_mode = not hasattr(self._engine, "ocr") and hasattr(self._engine, "predict")

    def close(self) -> None:
        self._temp_dir.cleanup()

    def recognize(self, image: np.ndarray) -> list[OcrLine]:
        if self._predict_mode:
            return self._recognize_with_predict(image)
        return self._recognize_with_ocr(image)

    def _recognize_with_ocr(self, image: np.ndarray) -> list[OcrLine]:
        try:
            raw = self._engine.ocr(image, cls=False)
        except TypeError:
            raw = self._engine.ocr(image)
        lines = self._parse_ocr_result(raw)
        if lines:
            return lines
        return self._parse_predict_result(raw)

    def _recognize_with_predict(self, image: np.ndarray) -> list[OcrLine]:
        temp_path = Path(self._temp_dir.name) / "frame.png"
        if not cv2.imwrite(str(temp_path), image):
            raise RuntimeError(f"Failed to save temporary OCR frame: {temp_path}")
        raw = self._engine.predict(input=str(temp_path))
        return self._parse_predict_result(raw)

    def _parse_ocr_result(self, raw: Any) -> list[OcrLine]:
        if raw is None:
            return []

        if isinstance(raw, dict):
            return self._parse_predict_result([raw])
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return self._parse_predict_result(raw)

        detections = raw
        if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], list):
            detections = raw[0]

        lines: list[OcrLine] = []
        for detection in detections or []:
            if not isinstance(detection, (list, tuple)) or len(detection) < 2:
                continue
            box = detection[0]
            rec = detection[1]
            if not isinstance(rec, (list, tuple)) or len(rec) < 2:
                continue
            text = str(rec[0]).strip()
            confidence = float(rec[1])
            if not text:
                continue
            lines.append(OcrLine(text=text, confidence=confidence, box=Rect.from_points(box)))
        return sorted(lines, key=lambda item: (item.box.y, item.box.x))

    def _parse_predict_result(self, raw: Any) -> list[OcrLine]:
        records = list(raw) if isinstance(raw, (list, tuple)) else [raw]
        lines: list[OcrLine] = []
        for record in records:
            payload = getattr(record, "res", None)
            if payload is None and isinstance(record, dict):
                payload = record.get("res", record)
            if payload is None:
                continue

            texts = _maybe_to_list(_payload_get(payload, "rec_texts"))
            scores = _maybe_to_list(_payload_get(payload, "rec_scores"))
            boxes = _maybe_to_list(
                _first_present(
                    _payload_get(payload, "rec_boxes"),
                    _payload_get(payload, "dt_polys"),
                    _payload_get(payload, "rec_polys"),
                )
            )
            for index, text in enumerate(texts):
                clean_text = str(text).strip()
                if not clean_text:
                    continue
                confidence = float(scores[index]) if index < len(scores) else 0.0
                box = boxes[index] if index < len(boxes) else [[0, 0], [1, 0], [1, 1], [0, 1]]
                lines.append(OcrLine(text=clean_text, confidence=confidence, box=_normalize_box(box)))
        return sorted(lines, key=lambda item: (item.box.y, item.box.x))


def _maybe_to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value)


def _payload_get(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        return payload.get(key)
    return getattr(payload, key, None)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_box(box: Any) -> Rect:
    if hasattr(box, "tolist"):
        box = box.tolist()
    if isinstance(box, list) and len(box) == 4 and not isinstance(box[0], (list, tuple)):
        x, y, width, height = [int(float(part)) for part in box]
        return Rect(x=x, y=y, width=max(1, width), height=max(1, height))
    return Rect.from_points(box)
