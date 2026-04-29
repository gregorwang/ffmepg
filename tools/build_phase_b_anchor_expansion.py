from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from phase_b_sequence_align import (
    ChineseCue,
    EnglishCue,
    build_context_texts,
    load_chinese_clip,
    load_english_units,
    monotonic_align,
    speaker_compatible,
)

MANUAL_EXCLUDE_SEGMENTS: dict[str, set[str]] = {
    "ghost-yotei-part01": {"blk_0232"},
    "ghost-yotei-part02": {"cue_01145", "blk_0494"},
}


@dataclass(slots=True)
class Anchor:
    part_name: str
    source_clip: str
    english_index: int
    chinese_pos: int
    payload: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Expand high-confidence bilingual anchors into local continuous windows."
    )
    parser.add_argument(
        "--anchor-json",
        type=Path,
        default=Path("scratch/phase_b_bilingual_hybrid_highconf_v1.json"),
    )
    parser.add_argument(
        "--chinese-ocr-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--english-ocr-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("scratch/phase_b_anchor_expansion_v1.json"),
    )
    parser.add_argument(
        "--output-tsv",
        type=Path,
        default=Path("scratch/phase_b_anchor_expansion_v1.tsv"),
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="paraphrase-multilingual-mpnet-base-v2",
    )
    parser.add_argument("--min-chinese-confidence", type=float, default=0.90)
    parser.add_argument("--context-window", type=int, default=1)
    parser.add_argument("--match-threshold", type=float, default=0.50)
    parser.add_argument("--output-threshold", type=float, default=0.58)
    parser.add_argument("--min-output-score", type=float, default=0.67)
    parser.add_argument("--skip-english-penalty", type=float, default=0.02)
    parser.add_argument("--skip-chinese-penalty", type=float, default=0.012)
    parser.add_argument("--progress-weight", type=float, default=0.14)
    parser.add_argument("--cluster-max-gap-seconds", type=float, default=120.0)
    parser.add_argument("--cluster-max-gap-cues", type=int, default=40)
    parser.add_argument("--flank-english", type=int, default=4)
    parser.add_argument("--flank-chinese", type=int, default=6)
    parser.add_argument("--max-region-english", type=int, default=20)
    parser.add_argument("--max-region-chinese", type=int, default=26)
    return parser.parse_args()


def load_anchor_groups(
    anchor_doc: dict[str, Any],
    english_index_by_id: dict[str, dict[str, int]],
    chinese_pos_by_key: dict[tuple[str, str], dict[int, int]],
) -> dict[tuple[str, str], list[Anchor]]:
    groups: dict[tuple[str, str], list[Anchor]] = defaultdict(list)
    for row in anchor_doc.get("flat_candidates") or []:
        part_name = str(row["part_name"])
        source_clip = str(row["source_clip"])
        english_id = str(row["id"])
        source_cue_index = int(row["source_cue_index"])
        english_index = english_index_by_id.get(part_name, {}).get(english_id)
        chinese_pos = chinese_pos_by_key.get((part_name, source_clip), {}).get(source_cue_index)
        if english_index is None or chinese_pos is None:
            continue
        groups[(part_name, source_clip)].append(
            Anchor(
                part_name=part_name,
                source_clip=source_clip,
                english_index=english_index,
                chinese_pos=chinese_pos,
                payload=row,
            )
        )
    for anchors in groups.values():
        anchors.sort(key=lambda item: (item.english_index, item.chinese_pos))
    return groups


def cluster_anchors(
    anchors: list[Anchor],
    english_units: list[EnglishCue],
    max_gap_seconds: float,
    max_gap_cues: int,
) -> list[list[Anchor]]:
    if not anchors:
        return []
    clusters: list[list[Anchor]] = [[anchors[0]]]
    for anchor in anchors[1:]:
        prev = clusters[-1][-1]
        english_gap = english_units[anchor.english_index].start - english_units[prev.english_index].start
        chinese_gap = anchor.chinese_pos - prev.chinese_pos
        if english_gap <= max_gap_seconds and chinese_gap <= max_gap_cues:
            clusters[-1].append(anchor)
        else:
            clusters.append([anchor])
    return clusters


def build_region_matches(
    model: SentenceTransformer,
    english_units: list[EnglishCue],
    chinese_cues: list[ChineseCue],
    english_start: int,
    english_end: int,
    chinese_start: int,
    chinese_end: int,
    context_window: int,
    match_threshold: float,
    output_threshold: float,
    min_output_score: float,
    skip_english_penalty: float,
    skip_chinese_penalty: float,
    progress_weight: float,
) -> list[tuple[int, int, float]]:
    if english_start > english_end or chinese_start > chinese_end:
        return []
    english_slice = english_units[english_start : english_end + 1]
    chinese_slice = chinese_cues[chinese_start : chinese_end + 1]
    if not english_slice or not chinese_slice:
        return []

    english_contexts = build_context_texts(
        [unit.semantic_text for unit in english_slice], context_window, 220
    )
    chinese_contexts = build_context_texts(
        [cue.semantic_text for cue in chinese_slice], max(1, context_window), 180
    )

    english_base = model.encode(
        [unit.semantic_text for unit in english_slice],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=128,
    )
    english_ctx = model.encode(
        english_contexts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=128,
    )
    chinese_base = model.encode(
        [cue.semantic_text for cue in chinese_slice],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=128,
    )
    chinese_ctx = model.encode(
        chinese_contexts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=128,
    )

    similarity = (0.35 * np.matmul(english_base, chinese_base.T)) + (
        0.65 * np.matmul(english_ctx, chinese_ctx.T)
    )
    similarity += progress_weight * build_local_progress_matrix(english_slice, chinese_slice)
    matches = monotonic_align(
        similarity=similarity,
        match_threshold=match_threshold,
        output_threshold=output_threshold,
        skip_english_penalty=skip_english_penalty,
        skip_chinese_penalty=skip_chinese_penalty,
        band_width=max(min(14, len(chinese_slice)), int(len(chinese_slice) * 0.65)),
    )
    accepted: list[tuple[int, int, float]] = []
    for local_english_index, local_chinese_index, score in matches:
        if score < min_output_score:
            continue
        accepted.append(
            (
                english_start + local_english_index,
                chinese_start + local_chinese_index,
                float(score),
            )
        )
    return accepted


def build_local_progress_matrix(
    english_units: list[EnglishCue],
    chinese_cues: list[ChineseCue],
) -> np.ndarray:
    if not english_units or not chinese_cues:
        return np.zeros((len(english_units), len(chinese_cues)), dtype=np.float32)
    eng_start = english_units[0].start
    eng_end = max(english_units[-1].end, eng_start + 1e-6)
    eng_denom = max(eng_end - eng_start, 1e-6)
    zh_start = chinese_cues[0].start
    zh_end = max(chinese_cues[-1].end, zh_start + 1e-6)
    zh_denom = max(zh_end - zh_start, 1e-6)
    eng_progress = np.array(
        [(((unit.start + unit.end) * 0.5) - eng_start) / eng_denom for unit in english_units],
        dtype=np.float32,
    )
    zh_progress = np.array(
        [(((cue.start + cue.end) * 0.5) - zh_start) / zh_denom for cue in chinese_cues],
        dtype=np.float32,
    )
    delta = np.abs(eng_progress[:, None] - zh_progress[None, :])
    return np.clip(1.0 - (delta / 0.30), 0.0, 1.0)


def add_match(
    rows_by_part: dict[str, dict[str, Any]],
    selected_ids: set[tuple[str, str]],
    part_name: str,
    english_unit: EnglishCue,
    chinese_cue: ChineseCue,
    score: float,
    source_version: str,
    mode: str,
    cluster_id: str,
) -> None:
    key = (part_name, english_unit.segment_id)
    existing = rows_by_part.setdefault(part_name, {}).get(english_unit.segment_id)
    if existing is not None and (existing.get("match_score") or 0.0) >= score:
        return
    payload = {
        "id": english_unit.segment_id,
        "segment_ids": english_unit.segment_ids,
        "start": round(english_unit.start, 3),
        "end": round(english_unit.end, 3),
        "english_text": english_unit.text,
        "chinese_text": clean_output_text(chinese_cue.text),
        "match_score": round(score, 4),
        "source_clip": chinese_cue.clip_name,
        "source_cue_index": chinese_cue.cue_index,
        "selection_version": source_version,
        "selection_mode": mode,
        "cluster_id": cluster_id,
        "part_name": part_name,
    }
    rows_by_part[part_name][english_unit.segment_id] = payload
    selected_ids.add(key)


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "\t".join(
            [
                "part_name",
                "selection_mode",
                "selection_version",
                "cluster_id",
                "match_score",
                "id",
                "source_clip",
                "source_cue_index",
                "start",
                "end",
                "english_text",
                "chinese_text",
            ]
        )
    ]
    for row in rows:
        lines.append(
            "\t".join(
                [
                    str(row.get("part_name", "")),
                    str(row.get("selection_mode", "")),
                    str(row.get("selection_version", "")),
                    str(row.get("cluster_id", "")),
                    f"{row.get('match_score', 0.0):.4f}",
                    str(row.get("id", "")),
                    str(row.get("source_clip", "")),
                    str(row.get("source_cue_index", "")),
                    str(row.get("start", "")),
                    str(row.get("end", "")),
                    str(row.get("english_text", "")).replace("\t", " ").replace("\n", " "),
                    str(row.get("chinese_text", "")).replace("\t", " ").replace("\n", " "),
                ]
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def clean_output_text(text: str) -> str:
    value = str(text).strip()
    value = value.rstrip("@#| ")
    return value.strip()


def main() -> None:
    args = parse_args()
    anchor_doc = json.loads(args.anchor_json.read_text(encoding="utf-8"))
    model = SentenceTransformer(args.model_name)

    english_units_by_part: dict[str, list[EnglishCue]] = {}
    english_index_by_id: dict[str, dict[str, int]] = {}
    chinese_cues_by_key: dict[tuple[str, str], list[ChineseCue]] = {}
    chinese_pos_by_key: dict[tuple[str, str], dict[int, int]] = {}

    anchor_part_names = sorted({str(row["part_name"]) for row in anchor_doc.get("flat_candidates") or []})
    for part_name in anchor_part_names:
        short_name = part_name.replace("ghost-yotei-", "")
        english_path = args.english_ocr_root / short_name / "cleaned.json"
        english_units = load_english_units(english_path)
        english_units_by_part[part_name] = english_units
        english_index_by_id[part_name] = {unit.segment_id: index for index, unit in enumerate(english_units)}

    clip_pairs = {
        (str(row["part_name"]), str(row["source_clip"]))
        for row in anchor_doc.get("flat_candidates") or []
    }
    for part_name, source_clip in clip_pairs:
        cues = [
            cue
            for cue in load_chinese_clip(args.chinese_ocr_root, source_clip)
            if cue.confidence >= args.min_chinese_confidence
        ]
        chinese_cues_by_key[(part_name, source_clip)] = cues
        chinese_pos_by_key[(part_name, source_clip)] = {
            cue.cue_index: pos for pos, cue in enumerate(cues)
        }

    anchor_groups = load_anchor_groups(anchor_doc, english_index_by_id, chinese_pos_by_key)
    rows_by_part: dict[str, dict[str, Any]] = {}
    selected_ids: set[tuple[str, str]] = set()

    for row in anchor_doc.get("flat_candidates") or []:
        part_name = str(row["part_name"])
        rows_by_part.setdefault(part_name, {})[str(row["id"])] = dict(row) | {
            "chinese_text": clean_output_text(str(row.get("chinese_text") or "")),
            "selection_mode": "anchor"
        }
        selected_ids.add((part_name, str(row["id"])))

    cluster_summaries: list[dict[str, Any]] = []

    for (part_name, source_clip), anchors in sorted(anchor_groups.items()):
        english_units = english_units_by_part[part_name]
        chinese_cues = chinese_cues_by_key[(part_name, source_clip)]
        clusters = cluster_anchors(
            anchors,
            english_units,
            max_gap_seconds=args.cluster_max_gap_seconds,
            max_gap_cues=args.cluster_max_gap_cues,
        )

        for cluster_index, cluster in enumerate(clusters, start=1):
            cluster_id = f"{part_name}:{source_clip}:cluster{cluster_index:02d}"
            cluster_added = 0
            first_anchor = cluster[0]
            last_anchor = cluster[-1]

            windows: list[tuple[int, int, int, int]] = []
            pre_eng_start = max(0, first_anchor.english_index - args.flank_english)
            pre_eng_end = first_anchor.english_index - 1
            pre_zh_start = max(0, first_anchor.chinese_pos - args.flank_chinese)
            pre_zh_end = first_anchor.chinese_pos - 1
            windows.append((pre_eng_start, pre_eng_end, pre_zh_start, pre_zh_end))

            for left_anchor, right_anchor in zip(cluster, cluster[1:]):
                windows.append(
                    (
                        left_anchor.english_index + 1,
                        right_anchor.english_index - 1,
                        left_anchor.chinese_pos + 1,
                        right_anchor.chinese_pos - 1,
                    )
                )

            post_eng_start = last_anchor.english_index + 1
            post_eng_end = min(len(english_units) - 1, last_anchor.english_index + args.flank_english)
            post_zh_start = last_anchor.chinese_pos + 1
            post_zh_end = min(len(chinese_cues) - 1, last_anchor.chinese_pos + args.flank_chinese)
            windows.append((post_eng_start, post_eng_end, post_zh_start, post_zh_end))

            source_version = str(cluster[0].payload.get("selection_version") or "")

            for english_start, english_end, chinese_start, chinese_end in windows:
                english_count = english_end - english_start + 1
                chinese_count = chinese_end - chinese_start + 1
                if english_count <= 0 or chinese_count <= 0:
                    continue
                if english_count > args.max_region_english or chinese_count > args.max_region_chinese:
                    continue
                matches = build_region_matches(
                    model=model,
                    english_units=english_units,
                    chinese_cues=chinese_cues,
                    english_start=english_start,
                    english_end=english_end,
                    chinese_start=chinese_start,
                    chinese_end=chinese_end,
                    context_window=args.context_window,
                    match_threshold=args.match_threshold,
                    output_threshold=args.output_threshold,
                    min_output_score=args.min_output_score,
                    skip_english_penalty=args.skip_english_penalty,
                    skip_chinese_penalty=args.skip_chinese_penalty,
                    progress_weight=args.progress_weight,
                )
                for english_index, chinese_pos, score in matches:
                    english_unit = english_units[english_index]
                    chinese_cue = chinese_cues[chinese_pos]
                    if not speaker_compatible(english_unit.text, chinese_cue.text):
                        continue
                    add_match(
                        rows_by_part=rows_by_part,
                        selected_ids=selected_ids,
                        part_name=part_name,
                        english_unit=english_unit,
                        chinese_cue=chinese_cue,
                        score=score,
                        source_version=source_version,
                        mode="expanded-local",
                        cluster_id=cluster_id,
                    )
                    cluster_added += 1

            cluster_summaries.append(
                {
                    "cluster_id": cluster_id,
                    "part_name": part_name,
                    "source_clip": source_clip,
                    "anchor_count": len(cluster),
                    "added_match_count": cluster_added,
                    "anchor_start": round(english_units[first_anchor.english_index].start, 3),
                    "anchor_end": round(english_units[last_anchor.english_index].end, 3),
                }
            )

    parts_output: list[dict[str, Any]] = []
    flat_rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for part_name in sorted(rows_by_part):
        rows = [
            row
            for row in rows_by_part[part_name].values()
            if str(row.get("id") or "") not in MANUAL_EXCLUDE_SEGMENTS.get(part_name, set())
        ]
        rows = sorted(
            rows,
            key=lambda item: (float(item.get("start") or 0.0), float(item.get("end") or 0.0), str(item.get("id") or "")),
        )
        parts_output.append(
            {
                "part_name": part_name,
                "segment_count": len(rows),
                "segments": rows,
            }
        )
        flat_rows.extend(rows)
        scores = [float(row["match_score"]) for row in rows if row.get("match_score") is not None]
        expanded_count = sum(1 for row in rows if row.get("selection_mode") == "expanded-local")
        summary.append(
            {
                "part_name": part_name,
                "candidate_count": len(rows),
                "anchor_count": len(rows) - expanded_count,
                "expanded_count": expanded_count,
                "mean_match_score": round(mean(scores), 4) if scores else None,
            }
        )

    payload = {
        "version": "phase-b-anchor-expansion-v1",
        "alignment_strategy": "hybrid high-confidence anchors + local monotonic expansion",
        "model_name": args.model_name,
        "parts": parts_output,
        "summary": summary,
        "cluster_summary": cluster_summaries,
        "flat_candidates": flat_rows,
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_tsv(args.output_tsv, flat_rows)

    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_tsv}")
    for item in summary:
        print(
            item["part_name"],
            f"candidates={item['candidate_count']}",
            f"anchors={item['anchor_count']}",
            f"expanded={item['expanded_count']}",
            f"mean={item['mean_match_score']}",
        )


if __name__ == "__main__":
    main()
