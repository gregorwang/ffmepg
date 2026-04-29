from __future__ import annotations

from .models import PreprocessProfile

DEFAULT_REGION_SAMPLE_COUNT = 24
DEFAULT_TUNE_SAMPLE_COUNT = 18
DEFAULT_EXTRACTION_FPS = 3.0
DEFAULT_MIN_CONFIDENCE = 0.45
DEFAULT_SIMILARITY_THRESHOLD = 0.86
DEFAULT_MAX_GAP_FRAMES = 1
DEFAULT_MIN_DURATION_SECONDS = 0.60


def build_default_profiles() -> list[PreprocessProfile]:
    return [
        PreprocessProfile(name="raw-color", grayscale=False),
        PreprocessProfile(name="gray-2x", scale=2.0, grayscale=True),
        PreprocessProfile(name="gray-2x-otsu", scale=2.0, grayscale=True, threshold_mode="otsu"),
        PreprocessProfile(
            name="gray-2x-adaptive",
            scale=2.0,
            grayscale=True,
            denoise_kernel=3,
            threshold_mode="adaptive",
        ),
        PreprocessProfile(
            name="gray-2x-adaptive-inv",
            scale=2.0,
            grayscale=True,
            denoise_kernel=3,
            threshold_mode="adaptive_inv",
        ),
        PreprocessProfile(
            name="sharp-2x-otsu",
            scale=2.0,
            grayscale=True,
            denoise_kernel=3,
            threshold_mode="otsu",
            sharpen=True,
        ),
        PreprocessProfile(
            name="contrast-2x-adaptive",
            scale=2.0,
            grayscale=True,
            denoise_kernel=3,
            threshold_mode="adaptive",
            contrast=1.2,
            brightness=10,
        ),
        PreprocessProfile(
            name="contrast-2x-close",
            scale=2.0,
            grayscale=True,
            denoise_kernel=3,
            threshold_mode="adaptive",
            morphology_close=2,
            contrast=1.25,
            brightness=12,
        ),
    ]
