from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_overlay(spec: str) -> dict[str, Any]:
    parts = spec.split("|")
    if len(parts) != 4:
        raise SystemExit(f"invalid overlay spec: {spec}")
    path_text, part_name, threshold_text, origins_text = parts
    origins = [item.strip() for item in origins_text.split(",") if item.strip()]
    if not origins:
        raise SystemExit(f"overlay origins cannot be empty: {spec}")
    return {
        "path": Path(path_text),
        "part_name": part_name.strip(),
        "threshold": float(threshold_text),
        "origins": origins,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge selected high-score overlay candidates back into the current Phase C base.")
    parser.add_argument("--base-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="Overlay rule: overlay_json|part_name|threshold|origin1,origin2",
    )
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> None:
    args = parse_args()
    overlay_rules = [parse_overlay(item) for item in args.overlay]
    if not overlay_rules:
        raise SystemExit("at least one --overlay is required")

    base_payload = json.loads(args.base_json.read_text(encoding="utf-8"))
    base_rows = [dict(row) for row in base_payload.get("segments") or []]
    rows_by_key = {(str(row["part_name"]), str(row["segment_id"])): row for row in base_rows}

    applied_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    used_segments: set[tuple[str, str]] = set()

    for rule in overlay_rules:
        payload = json.loads(rule["path"].read_text(encoding="utf-8"))
        for row in payload.get("segments") or []:
            segment_id = str(row.get("segment_id") or "")
            part_name = str(row.get("part_name") or "")
            key = (part_name, segment_id)
            if not segment_id or not part_name or key in used_segments:
                continue
            if part_name != rule["part_name"]:
                continue
            origin = str(row.get("match_origin") or "")
            score = float(row.get("match_score") or 0.0)
            if origin not in rule["origins"] or score < float(rule["threshold"]):
                continue
            base_row = rows_by_key.get(key)
            if base_row is None:
                continue
            if str(base_row.get("status") or "") != "unmatched":
                skipped_rows.append(
                    {
                        "segment_id": segment_id,
                        "part_name": base_row.get("part_name"),
                        "reason": "base-not-unmatched",
                        "overlay_path": str(rule["path"]),
                        "origin": origin,
                        "score": score,
                    }
                )
                continue
            rows_by_key[key] = dict(row)
            used_segments.add(key)
            applied_rows.append(
                {
                    "segment_id": segment_id,
                    "part_name": part_name,
                    "overlay_path": str(rule["path"]),
                    "origin": origin,
                    "score": score,
                    "english_text": row.get("english_text"),
                    "chinese_text": row.get("chinese_text"),
                }
            )

    merged_rows = sorted(rows_by_key.values(), key=lambda item: (item["part_name"], float(item["start"]), float(item["end"]), item["segment_id"]))
    matched_cues = sum(1 for row in merged_rows if str(row.get("status") or "") != "unmatched")
    total_rows = len(merged_rows)
    status_counts = Counter(str(row.get("status") or "unmatched") for row in merged_rows)
    part_counts: dict[str, dict[str, Any]] = {}
    for row in merged_rows:
        part_name = str(row["part_name"])
        payload = part_counts.setdefault(part_name, {"segment_count": 0, "matched_count": 0})
        payload["segment_count"] += 1
        if str(row.get("status") or "") != "unmatched":
            payload["matched_count"] += 1

    manifest = {
        "version": args.output_dir.name,
        "base_json": str(args.base_json),
        "overlay_rules": [
            {
                "path": str(rule["path"]),
                "part_name": rule["part_name"],
                "threshold": rule["threshold"],
                "origins": list(rule["origins"]),
            }
            for rule in overlay_rules
        ],
        "total_english_cues": total_rows,
        "matched_cues": matched_cues,
        "coverage_ratio": round(matched_cues / max(total_rows, 1), 4),
        "applied_row_count": len(applied_rows),
        "skipped_row_count": len(skipped_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "applied_origin_counts": dict(sorted(Counter(str(row["origin"]) for row in applied_rows).items())),
        "parts": [
            {
                "part_name": part_name,
                "segment_count": payload["segment_count"],
                "matched_count": payload["matched_count"],
                "coverage_ratio": round(payload["matched_count"] / max(payload["segment_count"], 1), 4),
            }
            for part_name, payload in sorted(part_counts.items())
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "manifest.json", manifest)
    write_json(args.output_dir / "all_segments.json", {"manifest": manifest, "segments": merged_rows})
    write_tsv(
        args.output_dir / "applied_rows.tsv",
        applied_rows,
        ["segment_id", "part_name", "overlay_path", "origin", "score", "english_text", "chinese_text"],
    )
    write_tsv(
        args.output_dir / "skipped_rows.tsv",
        skipped_rows,
        ["segment_id", "part_name", "reason", "overlay_path", "origin", "score"],
    )
    print(json.dumps({"output_dir": str(args.output_dir), "applied": len(applied_rows), "matched_cues": matched_cues}, ensure_ascii=False))


if __name__ == "__main__":
    main()
