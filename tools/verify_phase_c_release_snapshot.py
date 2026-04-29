from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT_DIR = Path("scratch/phase_c_release_snapshot_v1_complete")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_release_verification_v1_complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a Phase C release snapshot against current on-disk artifacts.")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
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


def main() -> None:
    args = parse_args()
    snapshot_manifest = load_json(args.snapshot_dir / "manifest.json")
    expected_rows = load_tsv(args.snapshot_dir / "artifact_checksums.tsv")

    verification_rows: list[dict[str, Any]] = []
    ok_count = 0
    missing_count = 0
    mismatch_count = 0

    for row in expected_rows:
        artifact = str(row.get("artifact") or "")
        resolved_file = Path(str(row.get("resolved_file") or ""))
        expected_exists = str(row.get("exists") or "").strip().lower() == "true"
        expected_size = str(row.get("size_bytes") or "")
        expected_sha256 = str(row.get("sha256") or "")

        actual_exists = resolved_file.exists()
        actual_size = str(resolved_file.stat().st_size) if actual_exists else ""
        actual_sha256 = sha256_file(resolved_file) if actual_exists else ""

        status = "ok"
        if expected_exists and not actual_exists:
            status = "missing"
            missing_count += 1
        elif actual_exists and (actual_size != expected_size or actual_sha256 != expected_sha256):
            status = "mismatch"
            mismatch_count += 1
        else:
            ok_count += 1

        verification_rows.append(
            {
                "artifact": artifact,
                "resolved_file": str(resolved_file),
                "expected_exists": expected_exists,
                "actual_exists": actual_exists,
                "expected_size": expected_size,
                "actual_size": actual_size,
                "expected_sha256": expected_sha256,
                "actual_sha256": actual_sha256,
                "status": status,
                "note": str(row.get("note") or ""),
            }
        )

    manifest = {
        "snapshot_dir": str(args.snapshot_dir),
        "snapshot_total_cue_count": snapshot_manifest.get("total_cue_count"),
        "snapshot_matched_cue_count": snapshot_manifest.get("matched_cue_count"),
        "snapshot_unmatched_cue_count": snapshot_manifest.get("unmatched_cue_count"),
        "artifact_count": len(verification_rows),
        "ok_count": ok_count,
        "missing_count": missing_count,
        "mismatch_count": mismatch_count,
        "verification_status": "ok" if missing_count == 0 and mismatch_count == 0 else "failed",
    }

    write_json(args.output_dir / "manifest.json", manifest)
    write_tsv(
        args.output_dir / "verification.tsv",
        verification_rows,
        [
            "artifact",
            "resolved_file",
            "expected_exists",
            "actual_exists",
            "expected_size",
            "actual_size",
            "expected_sha256",
            "actual_sha256",
            "status",
            "note",
        ],
    )
    write_json(args.output_dir / "verification.json", {"manifest": manifest, "rows": verification_rows})
    report_lines = [
        "# Phase C Release Verification",
        "",
        f"- Snapshot dir: `{manifest['snapshot_dir']}`",
        f"- Artifact count: `{manifest['artifact_count']}`",
        f"- OK count: `{manifest['ok_count']}`",
        f"- Missing count: `{manifest['missing_count']}`",
        f"- Mismatch count: `{manifest['mismatch_count']}`",
        f"- Verification status: `{manifest['verification_status']}`",
        "",
    ]
    (args.output_dir / "REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(f"wrote phase c release verification -> {args.output_dir}")


if __name__ == "__main__":
    main()
