from __future__ import annotations

import unittest

from game_subtitle_ocr.models import FrameSubtitleResult
from game_subtitle_ocr.postprocess import cues_to_srt, merge_frame_results


class PostprocessTests(unittest.TestCase):
    def test_merge_adjacent_duplicate_frames_into_one_cue(self) -> None:
        frames = [
            FrameSubtitleResult(frame_index=0, timestamp_seconds=0.0, text="你好", confidence=0.95, line_count=1),
            FrameSubtitleResult(frame_index=1, timestamp_seconds=0.5, text="你好", confidence=0.91, line_count=1),
            FrameSubtitleResult(frame_index=2, timestamp_seconds=1.0, text="", confidence=0.0, line_count=0),
            FrameSubtitleResult(frame_index=3, timestamp_seconds=1.5, text="", confidence=0.0, line_count=0),
        ]

        cues = merge_frame_results(
            frames=frames,
            frame_interval_seconds=0.5,
            similarity_threshold=0.85,
            max_gap_frames=1,
            min_duration_seconds=0.6,
        )

        self.assertEqual(1, len(cues))
        self.assertEqual("你好", cues[0].text)
        self.assertEqual(0.0, cues[0].start_seconds)
        self.assertGreaterEqual(cues[0].end_seconds, 1.0)

    def test_srt_rendering(self) -> None:
        frames = [
            FrameSubtitleResult(frame_index=0, timestamp_seconds=0.0, text="第一句", confidence=0.9, line_count=1),
            FrameSubtitleResult(frame_index=1, timestamp_seconds=0.5, text="", confidence=0.0, line_count=0),
            FrameSubtitleResult(frame_index=2, timestamp_seconds=1.0, text="第二句", confidence=0.9, line_count=1),
        ]
        cues = merge_frame_results(
            frames=frames,
            frame_interval_seconds=0.5,
            similarity_threshold=0.85,
            max_gap_frames=0,
            min_duration_seconds=0.5,
        )
        srt = cues_to_srt(cues)
        self.assertIn("00:00:00,000 -->", srt)
        self.assertIn("第一句", srt)
        self.assertIn("第二句", srt)


if __name__ == "__main__":
    unittest.main()
