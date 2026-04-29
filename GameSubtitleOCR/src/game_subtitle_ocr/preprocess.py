from __future__ import annotations

import cv2
import numpy as np

from .models import PreprocessProfile, Rect


def crop_image(image: np.ndarray, crop: Rect | None) -> np.ndarray:
    if crop is None:
        return image.copy()
    clamped = crop.clamp(image.shape[1], image.shape[0])
    return image[clamped.y : clamped.bottom, clamped.x : clamped.right].copy()


def apply_preprocess(
    image: np.ndarray,
    profile: PreprocessProfile,
    crop: Rect | None = None,
) -> np.ndarray:
    prepared = crop_image(image, crop)

    if profile.contrast != 1.0 or profile.brightness != 0:
        prepared = cv2.convertScaleAbs(prepared, alpha=profile.contrast, beta=profile.brightness)

    if profile.scale != 1.0:
        prepared = cv2.resize(
            prepared,
            dsize=None,
            fx=profile.scale,
            fy=profile.scale,
            interpolation=cv2.INTER_CUBIC,
        )

    if profile.grayscale:
        gray = cv2.cvtColor(prepared, cv2.COLOR_BGR2GRAY)
    else:
        gray = prepared

    if profile.denoise_kernel and profile.denoise_kernel >= 3:
        gray = cv2.GaussianBlur(gray, (profile.denoise_kernel, profile.denoise_kernel), 0)

    if profile.sharpen:
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        gray = cv2.filter2D(gray, -1, kernel)

    if isinstance(gray, np.ndarray) and len(gray.shape) == 2:
        gray = apply_threshold(gray, profile.threshold_mode)
        if profile.invert:
            gray = cv2.bitwise_not(gray)
        if profile.morphology_close > 0:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT, (profile.morphology_close, profile.morphology_close)
            )
            gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    return gray


def apply_threshold(gray: np.ndarray, mode: str) -> np.ndarray:
    if mode == "none":
        return gray
    if mode == "otsu":
        _, output = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return output
    if mode == "adaptive":
        return cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
    if mode == "adaptive_inv":
        return cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            11,
        )
    raise ValueError(f"Unsupported threshold mode: {mode}")
