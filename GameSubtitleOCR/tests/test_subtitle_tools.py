from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from game_subtitle_ocr.models import Rect, SubtitleCue
from game_subtitle_ocr.subtitle_tools import (
    align_english_transcript_to_chinese,
    clean_subtitle_cues,
    load_cues_from_path,
    parse_srt,
    prepare_audit_dataset,
    score_audit_dataset,
    write_cues_json,
)


class SubtitleToolsTests(unittest.TestCase):
    def test_parse_srt_and_clean_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.srt"
            path.write_text(
                "\n".join(
                    [
                        "1",
                        "00:00:01,000 --> 00:00:02,000",
                        "笃：(呼吸起伏)",
                        "",
                        "2",
                        "00:00:01,500 --> 00:00:02,500",
                        "笃： (呼吸起伏)",
                        "",
                        "3",
                        "00:00:03,000 --> 00:00:03,400",
                        "斋藤匪徒：",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            parsed = parse_srt(path)
            cleaned = clean_subtitle_cues(parsed)

            self.assertEqual(3, len(parsed))
            self.assertEqual(1, len(cleaned))
            self.assertEqual("笃：(呼吸起伏)", cleaned[0].text)

    def test_drop_bridge_cue(self) -> None:
        cues = [
            SubtitleCue(index=1, start_seconds=1.0, end_seconds=2.0, text="笃：等会儿吧。", confidence=1.0),
            SubtitleCue(index=2, start_seconds=2.0, end_seconds=2.6, text="笃：等会儿吧。 笃：母亲催我呢", confidence=1.0),
            SubtitleCue(index=3, start_seconds=2.5, end_seconds=3.5, text="笃：母亲催我呢。", confidence=1.0),
        ]

        cleaned = clean_subtitle_cues(cues)
        self.assertEqual(2, len(cleaned))
        self.assertEqual("笃：等会儿吧。", cleaned[0].text)
        self.assertEqual("笃：母亲催我呢。", cleaned[1].text)

    def test_align_english_json_to_chinese_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            english_path = temp_path / "english.json"
            chinese_path = temp_path / "chinese.json"
            output_path = temp_path / "bilingual.json"

            english_path.write_text(
                json.dumps(
                    {
                        "Segments": [
                            {"Id": "dlg_00001", "Start": 10.0, "End": 12.0, "Text": "hello there"},
                            {"Id": "dlg_00002", "Start": 14.0, "End": 16.0, "Text": "general kenobi"},
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            chinese_path.write_text(
                json.dumps(
                    {
                        "cues": [
                            {"index": 1, "start": 10.3, "end": 11.8, "text": "你好啊"},
                            {"index": 2, "start": 14.4, "end": 15.6, "text": "将军"},
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            align_english_transcript_to_chinese(english_path, chinese_path, output_path, max_offset_seconds=1.0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(2, len(payload["segments"]))
            self.assertEqual("你好啊", payload["segments"][0]["chinese_text"])
            self.assertEqual("将军", payload["segments"][1]["chinese_text"])

    def test_write_cues_json_keeps_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_path = temp_path / "cues.json"

            write_cues_json(
                output_path=output_path,
                source_path=Path("sample.mp4"),
                cues=[
                    SubtitleCue(
                        index=1,
                        start_seconds=1.25,
                        end_seconds=2.5,
                        text="斋藤匪徒：让它瞎蹦！",
                        confidence=0.97321,
                    )
                ],
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(1, payload["cue_count"])
            self.assertEqual("斋藤匪徒：让它瞎蹦！", payload["cues"][0]["text"])
            self.assertEqual(0.9732, payload["cues"][0]["confidence"])

    def test_clean_subtitle_cues_drops_low_confidence_short_fragments(self) -> None:
        cues = [
            SubtitleCue(index=1, start_seconds=1.0, end_seconds=1.8, text="斋藤匪徒：让它瞎蹦！", confidence=0.96),
            SubtitleCue(index=2, start_seconds=2.0, end_seconds=2.8, text="客藤匪佳", confidence=0.52),
            SubtitleCue(index=3, start_seconds=3.0, end_seconds=3.8, text="村民：快进屋里去。", confidence=0.99),
        ]

        cleaned = clean_subtitle_cues(cues, min_confidence=0.60)

        self.assertEqual(2, len(cleaned))
        self.assertEqual("斋藤匪徒：让它瞎蹦！", cleaned[0].text)
        self.assertEqual("村民：快进屋里去。", cleaned[1].text)

    def test_clean_subtitle_cues_drops_low_confidence_short_duration_candidate(self) -> None:
        cues = [
            SubtitleCue(index=1, start_seconds=1.0, end_seconds=2.5, text="村民：快进屋里去。", confidence=0.99),
            SubtitleCue(index=2, start_seconds=3.0, end_seconds=3.8, text="谦吾：有时候：冲刺政翻滚才定上策。", confidence=0.7055),
            SubtitleCue(index=3, start_seconds=4.0, end_seconds=5.5, text="笃：我才不怕你！", confidence=0.97),
        ]

        cleaned = clean_subtitle_cues(cues, min_confidence=0.75)

        self.assertEqual(2, len(cleaned))
        self.assertEqual("村民：快进屋里去。", cleaned[0].text)
        self.assertEqual("笃：我才不怕你！", cleaned[1].text)

    def test_load_cues_from_json_preserves_confidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "raw.json"
            input_path.write_text(
                json.dumps(
                    {
                        "cues": [
                            {
                                "index": 1,
                                "start": 10.0,
                                "end": 11.2,
                                "text": "村民：快进屋里去。",
                                "confidence": 0.88,
                            }
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            cues = load_cues_from_path(input_path)

            self.assertEqual(1, len(cues))
            self.assertEqual(0.88, cues[0].confidence)

    def test_clean_subtitle_cues_collapses_dense_overlap_cluster(self) -> None:
        cues = [
            SubtitleCue(index=1, start_seconds=25.0, end_seconds=25.8, text="金滕匪徒： 笑）真蠢！", confidence=0.82),
            SubtitleCue(index=2, start_seconds=25.25, end_seconds=26.05, text="斋滕匪徒： （关）具蠢！", confidence=0.78),
            SubtitleCue(index=3, start_seconds=26.25, end_seconds=27.05, text="需膝匪促", confidence=0.64),
            SubtitleCue(index=4, start_seconds=27.0, end_seconds=27.8, text="齐藤匪徒 直春", confidence=0.86),
            SubtitleCue(index=5, start_seconds=27.5, end_seconds=28.3, text="斋藤匪徒： 笑）直春", confidence=0.86),
            SubtitleCue(index=6, start_seconds=28.0, end_seconds=28.8, text="斋藤匪徒： （笑）真蠢！", confidence=0.89),
            SubtitleCue(index=7, start_seconds=28.25, end_seconds=29.05, text="（笑）真蠢！ 斋藤匪徒：", confidence=0.94),
            SubtitleCue(index=8, start_seconds=28.5, end_seconds=29.3, text="斋藤匪徒： （笑）真蠢！", confidence=0.94),
        ]

        cleaned = clean_subtitle_cues(cues, similarity_threshold=0.78, min_confidence=0.60)

        self.assertEqual(1, len(cleaned))
        self.assertEqual("斋藤匪徒： （笑）真蠢！", cleaned[0].text)

    def test_clean_subtitle_cues_drops_gameplay_prompt(self) -> None:
        cues = [
            SubtitleCue(index=1, start_seconds=1.0, end_seconds=4.0, text="查看：按住", confidence=0.98),
            SubtitleCue(index=2, start_seconds=5.0, end_seconds=6.5, text="村民：快进屋里去。", confidence=0.99),
        ]

        cleaned = clean_subtitle_cues(cues, min_confidence=0.75)

        self.assertEqual(1, len(cleaned))
        self.assertEqual("村民：快进屋里去。", cleaned[0].text)

    def test_clean_subtitle_cues_drops_english_uppercase_ui_prompt(self) -> None:
        cues = [
            SubtitleCue(index=1, start_seconds=1.0, end_seconds=2.0, text="OPEN SPYGLASS", confidence=0.98),
            SubtitleCue(index=2, start_seconds=2.0, end_seconds=3.0, text="YOTEI RIVER", confidence=0.99),
            SubtitleCue(index=3, start_seconds=3.0, end_seconds=5.0, text="Atsu: Time to get their attention.", confidence=0.99),
        ]

        cleaned = clean_subtitle_cues(cues, min_confidence=0.75, language="en")

        self.assertEqual(1, len(cleaned))
        self.assertEqual("Atsu: Time to get their attention.", cleaned[0].text)

    def test_prepare_audit_dataset_adds_review_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cues_path = temp_path / "cleaned.json"
            output_path = temp_path / "audit_50.json"
            cues_path.write_text(
                json.dumps(
                    {
                        "cues": [
                            {"index": 1, "start": 1.0, "end": 2.0, "text": "第一句", "confidence": 0.91},
                            {"index": 2, "start": 3.0, "end": 4.0, "text": "第二句", "confidence": 0.92},
                            {"index": 3, "start": 5.0, "end": 6.0, "text": "第三句", "confidence": 0.93},
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            payload = prepare_audit_dataset(
                cues_path=cues_path,
                output_path=output_path,
                sample_count=2,
                source_video_path=None,
                crop=Rect(x=128, y=525, width=1024, height=129),
            )

            self.assertEqual(2, payload["sample_count"])
            self.assertEqual(2, len(payload["items"]))
            self.assertEqual("", payload["items"][0]["reference_text"])
            self.assertIsNone(payload["items"][0]["accepted"])
            self.assertEqual("", payload["items"][0]["notes"])
            self.assertIsNone(payload["items"][0]["image"])

    def test_score_audit_dataset_computes_average_character_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            audit_path = temp_path / "audit_50.json"
            report_path = temp_path / "audit_report.json"
            audit_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "audit_index": 1,
                                "cue_id": "cue_00001",
                                "text": "村民：快进屋里去。",
                                "reference_text": "村民：快进屋里去。",
                            },
                            {
                                "audit_index": 2,
                                "cue_id": "cue_00002",
                                "text": "笃：蜘蛛。",
                                "reference_text": "笃：蜘珠。",
                            },
                            {
                                "audit_index": 3,
                                "cue_id": "cue_00003",
                                "text": "斋藤匪徒：让它瞎蹦！",
                                "reference_text": "",
                            },
                        ]
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            report = score_audit_dataset(audit_path, output_path=report_path, pass_threshold=0.90)

            self.assertEqual(3, report["total_items"])
            self.assertEqual(2, report["scored_items"])
            self.assertEqual(1, report["missing_reference_items"])
            self.assertAlmostEqual(0.9, report["average_character_accuracy"], places=4)
            self.assertFalse(report["passed"])
            self.assertEqual(2, report["worst_items"][0]["audit_index"])


if __name__ == "__main__":
    unittest.main()
