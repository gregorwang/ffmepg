from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split Phase B medium-priority curation items into review batches."
    )
    parser.add_argument("--curation-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "curation_id",
        "part_name",
        "quality_label",
        "selection_mode",
        "source_clip",
        "start",
        "end",
        "match_score",
        "english_text",
        "chinese_text",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Phase B Medium Review Batches",
        "",
        "这批次是 `curation_pack_v1` 里剩余的 `78` 条中优先级条目。",
        "它们尚未进入人工 patch 回写流程，因此当前在 reviewed master 中仍是 `needs-review`。",
        "",
        "## 分批原则",
        "",
        "- 不强行按条数平均切分",
        "- 优先按 part 和问题面保持一致",
        "- `part03` 单独再拆成两半，避免一次 review 过长",
        "",
        "## 批次",
        "",
    ]
    for batch in manifest["batches"]:
        lines.append(f"- `{batch['name']}`: `{batch['item_count']}` 条, `{batch['scope_note']}`")
    lines.extend(
        [
            "",
            "## 文件",
            "",
            "- `<batch>.json`: 机器可读批次",
            "- `<batch>.tsv`: 快速浏览版",
            "- `manifest.json`: 批次总览",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["part_name"], row["start"], row["end"], row["curation_id"]))


def main() -> None:
    args = parse_args()
    payload = json.loads(args.curation_json.read_text(encoding="utf-8"))
    all_rows = list(payload.get("segments") or [])
    medium_rows = [row for row in all_rows if row.get("priority") == "medium"]

    part01_rows = sort_rows([row for row in medium_rows if row["part_name"] == "ghost-yotei-part01"])
    part02_rows = sort_rows([row for row in medium_rows if row["part_name"] == "ghost-yotei-part02"])
    part04_rows = sort_rows([row for row in medium_rows if row["part_name"] == "ghost-yotei-part04"])
    part03_rows = sort_rows([row for row in medium_rows if row["part_name"] == "ghost-yotei-part03"])

    midpoint = (len(part03_rows) + 1) // 2
    batches = [
        {
            "name": "medium_batch_01_part01_accepted",
            "rows": part01_rows,
            "scope_note": "part01 accepted-low-score cue-local rows",
        },
        {
            "name": "medium_batch_02_part02_accepted",
            "rows": part02_rows,
            "scope_note": "part02 accepted-low-score cue-local rows",
        },
        {
            "name": "medium_batch_03_part04_partial",
            "rows": part04_rows,
            "scope_note": "part04 partial filter-mapped rows",
        },
        {
            "name": "medium_batch_04_part03_partial_a",
            "rows": part03_rows[:midpoint],
            "scope_note": "part03 partial rows, early half",
        },
        {
            "name": "medium_batch_05_part03_partial_b",
            "rows": part03_rows[midpoint:],
            "scope_note": "part03 partial rows, late half",
        },
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "phase-b-medium-review-batches-v1",
        "source_curation_json": str(args.curation_json),
        "source_medium_item_count": len(medium_rows),
        "batches": [],
    }

    for batch in batches:
        rows = batch["rows"]
        batch_payload = {
            "name": batch["name"],
            "scope_note": batch["scope_note"],
            "item_count": len(rows),
            "items": rows,
        }
        write_json(args.output_dir / f"{batch['name']}.json", batch_payload)
        write_tsv(args.output_dir / f"{batch['name']}.tsv", rows)
        manifest["batches"].append(
            {
                "name": batch["name"],
                "item_count": len(rows),
                "parts": sorted({row["part_name"].replace("ghost-yotei-", "") for row in rows}),
                "scope_note": batch["scope_note"],
            }
        )

    write_json(args.output_dir / "manifest.json", manifest)
    write_readme(args.output_dir / "README.md", manifest)
    print(f"wrote medium review batches -> {args.output_dir}")


if __name__ == "__main__":
    main()
