from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_MASTER_DELIVERY_DIR = Path("scratch/phase_c_master_delivery_v1_complete")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_release_snapshot_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a lightweight frozen release snapshot for the completed Phase C deliverable.")
    parser.add_argument("--master-delivery-dir", type=Path, default=DEFAULT_MASTER_DELIVERY_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_file_path(path: Path) -> Path | None:
    if path.is_file():
        return path
    if path.is_dir():
        for name in ["manifest.json", "README.md", "all_segments.json", "handoff.json"]:
            candidate = path / name
            if candidate.exists():
                return candidate
    return None


def write_readme(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Ghost Yotei Phase C Release Snapshot",
        "",
        f"- Source master delivery: `{manifest['master_delivery_dir']}`",
        f"- Total cues: `{manifest['total_cue_count']}`",
        f"- Matched cues: `{manifest['matched_cue_count']}`",
        f"- Unmatched cues: `{manifest['unmatched_cue_count']}`",
        f"- Coverage ratio: `{manifest['coverage_ratio']}`",
        f"- Remaining model requests: `{manifest['remaining_model_requests']}`",
        "",
        "## Files",
        "",
        "- `manifest.json`: frozen top-level snapshot summary",
        "- `artifact_checksums.tsv`: sha256 + size for key referenced files",
        "- `artifact_paths.tsv`: direct artifact entry points copied from master delivery",
        "- `OPEN_ARTIFACTS.ps1`: convenience script to print the key paths",
        "",
        "This snapshot does not duplicate large delivery assets. It freezes references and checksums only.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    master_manifest = load_json(args.master_delivery_dir / "manifest.json")
    path_rows = load_tsv(args.master_delivery_dir / "paths.tsv")

    checksum_rows: list[dict[str, Any]] = []
    for row in path_rows:
        artifact = str(row.get("artifact") or "")
        raw_path = str(row.get("path") or "")
        note = str(row.get("note") or "")
        path_obj = Path(raw_path)
        actual_file = candidate_file_path(path_obj)
        checksum_rows.append(
            {
                "artifact": artifact,
                "path": raw_path,
                "resolved_file": str(actual_file) if actual_file else "",
                "exists": bool(actual_file and actual_file.exists()),
                "size_bytes": actual_file.stat().st_size if actual_file and actual_file.exists() else "",
                "sha256": sha256_file(actual_file) if actual_file and actual_file.exists() else "",
                "note": note,
            }
        )

    manifest = {
        "master_delivery_dir": str(args.master_delivery_dir),
        "total_cue_count": master_manifest.get("total_cue_count"),
        "matched_cue_count": master_manifest.get("matched_cue_count"),
        "unmatched_cue_count": master_manifest.get("unmatched_cue_count"),
        "coverage_ratio": master_manifest.get("coverage_ratio"),
        "remaining_model_requests": master_manifest.get("remaining_model_requests"),
        "decision_counts": dict(master_manifest.get("decision_counts") or {}),
        "changed_row_count_vs_base": master_manifest.get("changed_row_count_vs_base"),
        "artifact_count": len(path_rows),
        "checksummed_file_count": sum(1 for row in checksum_rows if row["exists"]),
    }

    write_json(args.output_dir / "manifest.json", manifest)
    write_tsv(args.output_dir / "artifact_paths.tsv", path_rows, ["artifact", "path", "note"])
    write_tsv(
        args.output_dir / "artifact_checksums.tsv",
        checksum_rows,
        ["artifact", "path", "resolved_file", "exists", "size_bytes", "sha256", "note"],
    )
    write_readme(args.output_dir / "README.md", manifest)
    open_script = [
        "$ErrorActionPreference = 'Stop'",
        f"Get-Content '{(args.output_dir / 'manifest.json').as_posix()}'",
        "",
        "# Key artifacts",
    ]
    for row in path_rows:
        open_script.append(f"Write-Output '{row['artifact']}: {row['path']}'")
    (args.output_dir / "OPEN_ARTIFACTS.ps1").write_text("\n".join(open_script) + "\n", encoding="utf-8")
    print(f"wrote phase c release snapshot -> {args.output_dir}")


if __name__ == "__main__":
    main()
