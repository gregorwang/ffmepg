from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_PHASE_C_DIR = Path("scratch/phase_c_model_applied_v1")
DEFAULT_PARTS_ROOT = Path("scratch")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_burnin_prep_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export burn-in preparation assets from a Phase C output directory.")
    parser.add_argument("--phase-c-dir", type=Path, default=DEFAULT_PHASE_C_DIR)
    parser.add_argument("--parts-root", type=Path, default=DEFAULT_PARTS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--version-label", type=str, default="phase-c-burnin-prep-v1")
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
        lines = [str(row.get("english_text") or "").strip()]
        chinese_text = str(row.get("chinese_text") or "").strip()
        if chinese_text:
            lines.append(chinese_text)
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{seconds_to_srt(float(row['start']))} --> {seconds_to_srt(float(row['end']))}",
                    "\n".join(line for line in lines if line),
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


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
    payload = json.loads((args.phase_c_dir / "all_segments.json").read_text(encoding="utf-8"))
    manifest = dict(payload.get("manifest") or {})
    segments = list(payload.get("segments") or [])
    part_rows: dict[str, list[dict[str, Any]]] = {}
    for row in segments:
        short_name = str(row.get("part_name") or "").split("-")[-1].replace("part", "part")
        part_rows.setdefault(short_name, []).append(row)

    entries: list[dict[str, Any]] = []
    for short_name, rows in sorted(part_rows.items()):
        subtitle_dir = args.output_dir / short_name
        subtitle_path = subtitle_dir / f"{short_name}.bilingual.srt"
        write_text(subtitle_path, render_bilingual_srt(rows))
        source_video = find_source_video(args.parts_root, short_name)
        burn_output = subtitle_dir / f"{short_name}.burned.mp4"
        entries.append(
            {
                "part": short_name,
                "segment_count": len(rows),
                "matched_count": sum(1 for row in rows if str(row.get("status") or "") != "unmatched"),
                "source_video": str(source_video) if source_video else None,
                "subtitle_srt": str(subtitle_path),
                "burn_output": str(burn_output),
                "burn_command": build_burn_command(source_video, subtitle_path, burn_output) if source_video else None,
            }
        )

    output_manifest = {
        "version": args.version_label,
        "source_phase_c_dir": str(args.phase_c_dir),
        "source_phase_c_version": manifest.get("version"),
        "parts_root": str(args.parts_root),
        "part_count": len(entries),
        "entries": entries,
    }
    write_json(args.output_dir / "manifest.json", output_manifest)

    commands = [
        "# Phase C Burn-in Commands",
        "",
        "# Run one command at a time or use the generated PowerShell helper.",
        "",
    ]
    ps_lines = [
        "$ErrorActionPreference = 'Stop'",
        "",
    ]
    for entry in entries:
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
                "# Phase C Burn-in Prep",
                "",
                f"- Version: `{args.version_label}`",
                f"- Source Phase C dir: `{args.phase_c_dir}`",
                f"- Parts root: `{args.parts_root}`",
                "",
                "This directory contains bilingual SRT files and ready-to-run ffmpeg burn-in commands.",
            ]
        )
        + "\n",
    )
    print(f"wrote phase c burn-in prep -> {args.output_dir}")


if __name__ == "__main__":
    main()
