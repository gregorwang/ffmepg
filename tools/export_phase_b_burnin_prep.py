from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export burn-in preparation assets from a reviewed Phase B final export."
    )
    parser.add_argument("--final-export-dir", type=Path, required=True)
    parser.add_argument("--parts-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--version-label",
        type=str,
        default="phase-b-burnin-prep-v1",
    )
    return parser.parse_args()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def seconds_to_srt(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def render_bilingual_srt(rows: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, row in enumerate(rows, start=1):
        text = f"{row['english_text']}\n{row['chinese_text']}"
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{seconds_to_srt(float(row['start']))} --> {seconds_to_srt(float(row['end']))}",
                    text.strip(),
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def find_source_video(parts_root: Path, short_name: str) -> Path | None:
    part_dir = parts_root / f"ghost-yotei-{short_name}"
    if not part_dir.exists():
        return None
    candidates = sorted(part_dir.glob("*.mp4"))
    return candidates[0] if candidates else None


def subtitle_filter_arg(path: Path) -> str:
    normalized = str(path.resolve()).replace("\\", "/").replace(":", "\\:")
    return f"subtitles='{normalized}'"


def build_burn_command(video_path: Path, subtitle_path: Path, output_path: Path) -> str:
    return (
        f'ffmpeg -y -i "{video_path}" -vf "{subtitle_filter_arg(subtitle_path)}" '
        f'-c:v libx264 -crf 18 -preset medium -c:a copy "{output_path}"'
    )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    final_manifest = json.loads((args.final_export_dir / "manifest.json").read_text(encoding="utf-8"))
    parts = sorted(final_manifest.get("parts_covered") or [])
    burn_entries: list[dict[str, str | int | None]] = []

    for short_name in parts:
        part_json = args.final_export_dir / short_name / f"{short_name}.bilingual.json"
        payload = json.loads(part_json.read_text(encoding="utf-8"))
        rows = list(payload.get("segments") or [])

        subtitle_dir = args.output_dir / short_name
        subtitle_path = subtitle_dir / f"{short_name}.bilingual.srt"
        write_text(subtitle_path, render_bilingual_srt(rows))

        source_video = find_source_video(args.parts_root, short_name)
        burn_output = subtitle_dir / f"{short_name}.burned.mp4"
        burn_entries.append(
            {
                "part": short_name,
                "segment_count": len(rows),
                "source_video": str(source_video) if source_video is not None else None,
                "subtitle_srt": str(subtitle_path),
                "burn_output": str(burn_output),
                "burn_command": build_burn_command(source_video, subtitle_path, burn_output) if source_video else None,
            }
        )

    manifest = {
        "version": args.version_label,
        "source_final_export_dir": str(args.final_export_dir),
        "parts_root": str(args.parts_root),
        "part_count": len(burn_entries),
        "entries": burn_entries,
    }
    write_json(args.output_dir / "manifest.json", manifest)

    commands = [
        "# Phase B Burn-in Commands",
        "",
        "# Run one command at a time or use the generated PowerShell helper.",
        "",
    ]
    ps_lines = [
        "$ErrorActionPreference = 'Stop'",
        "",
    ]
    for entry in burn_entries:
        commands.append(f"# {entry['part']}")
        commands.append(entry["burn_command"] or "# source video not found")
        commands.append("")
        if entry["burn_command"]:
            ps_lines.append(entry["burn_command"])
            ps_lines.append("")

    write_text(args.output_dir / "burn_commands.txt", "\n".join(commands).strip() + "\n")
    write_text(args.output_dir / "burn_commands.ps1", "\n".join(ps_lines).strip() + "\n")
    write_text(
        args.output_dir / "README.md",
        "\n".join(
            [
                "# Phase B Burn-in Prep",
                "",
                f"- Version: `{args.version_label}`",
                f"- Source final export: `{args.final_export_dir}`",
                f"- Parts root: `{args.parts_root}`",
                "",
                "This directory contains bilingual SRT files and ready-to-run ffmpeg burn-in commands.",
            ]
        )
        + "\n",
    )
    print(f"wrote burn-in prep -> {args.output_dir}")


if __name__ == "__main__":
    main()
