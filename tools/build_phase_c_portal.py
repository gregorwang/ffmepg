from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_DASHBOARD_DIR = Path("scratch/phase_c_dashboard_v1_complete")
DEFAULT_COMPLETION_REPORT_DIR = Path("scratch/phase_c_completion_report_v1_complete")
DEFAULT_RELEASE_VERIFICATION_DIR = Path("scratch/phase_c_release_verification_v1_complete")
DEFAULT_RELEASE_SNAPSHOT_DIR = Path("scratch/phase_c_release_snapshot_v1_complete")
DEFAULT_MASTER_DELIVERY_DIR = Path("scratch/phase_c_master_delivery_v1_complete")
DEFAULT_DELIVERY_PACK_DIR = Path("scratch/phase_c_delivery_pack_v1_complete")
DEFAULT_BURNIN_DIR = Path("scratch/phase_c_burnin_prep_v3_complete")
DEFAULT_HANDOFF_JSON = Path("scratch/phase_c_model_handoff_v3_complete/handoff.json")
DEFAULT_DELTA_DIR = Path("scratch/phase_c_predecision_delta_pack_v4_complete_vs_base")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_portal_v1_complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a final navigation portal for the completed Phase C deliverable.")
    parser.add_argument("--dashboard-dir", type=Path, default=DEFAULT_DASHBOARD_DIR)
    parser.add_argument("--completion-report-dir", type=Path, default=DEFAULT_COMPLETION_REPORT_DIR)
    parser.add_argument("--release-verification-dir", type=Path, default=DEFAULT_RELEASE_VERIFICATION_DIR)
    parser.add_argument("--release-snapshot-dir", type=Path, default=DEFAULT_RELEASE_SNAPSHOT_DIR)
    parser.add_argument("--master-delivery-dir", type=Path, default=DEFAULT_MASTER_DELIVERY_DIR)
    parser.add_argument("--delivery-pack-dir", type=Path, default=DEFAULT_DELIVERY_PACK_DIR)
    parser.add_argument("--burnin-dir", type=Path, default=DEFAULT_BURNIN_DIR)
    parser.add_argument("--handoff-json", type=Path, default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--delta-dir", type=Path, default=DEFAULT_DELTA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    completion_manifest = load_json(args.completion_report_dir / "manifest.json")
    verification_manifest = load_json(args.release_verification_dir / "manifest.json")

    portal = {
        "headline": {
            "total_cue_count": completion_manifest.get("total_cue_count"),
            "matched_cue_count": completion_manifest.get("matched_cue_count"),
            "unmatched_cue_count": completion_manifest.get("unmatched_cue_count"),
            "coverage_ratio": completion_manifest.get("coverage_ratio"),
            "remaining_model_requests": completion_manifest.get("remaining_model_requests"),
            "verification_status": verification_manifest.get("verification_status"),
        },
        "artifacts": {
            "dashboard_dir": str(args.dashboard_dir),
            "dashboard_page": str(args.dashboard_dir / "index.html"),
            "completion_report_dir": str(args.completion_report_dir),
            "completion_summary": str(args.completion_report_dir / "REPORT.md"),
            "release_verification_dir": str(args.release_verification_dir),
            "release_verification_summary": str(args.release_verification_dir / "REPORT.md"),
            "release_snapshot_dir": str(args.release_snapshot_dir),
            "master_delivery_dir": str(args.master_delivery_dir),
            "delivery_pack_dir": str(args.delivery_pack_dir),
            "burnin_dir": str(args.burnin_dir),
            "handoff_json": str(args.handoff_json),
            "delta_dir": str(args.delta_dir),
        },
    }
    write_json(args.output_dir / "portal.json", portal)

    portal_md = "\n".join(
        [
            "# Ghost Yotei Phase C Portal",
            "",
            "## Headline",
            "",
            f"- Total cues: `{portal['headline']['total_cue_count']}`",
            f"- Matched cues: `{portal['headline']['matched_cue_count']}`",
            f"- Unmatched cues: `{portal['headline']['unmatched_cue_count']}`",
            f"- Coverage ratio: `{portal['headline']['coverage_ratio']}`",
            f"- Remaining model requests: `{portal['headline']['remaining_model_requests']}`",
            f"- Verification status: `{portal['headline']['verification_status']}`",
            "",
            "## Entry Points",
            "",
            f"- Dashboard: `{portal['artifacts']['dashboard_page']}`",
            f"- Completion report: `{portal['artifacts']['completion_summary']}`",
            f"- Release verification: `{portal['artifacts']['release_verification_summary']}`",
            f"- Release snapshot: `{portal['artifacts']['release_snapshot_dir']}`",
            f"- Master delivery: `{portal['artifacts']['master_delivery_dir']}`",
            f"- Delivery pack: `{portal['artifacts']['delivery_pack_dir']}`",
            f"- Burn-in prep: `{portal['artifacts']['burnin_dir']}`",
            f"- Handoff: `{portal['artifacts']['handoff_json']}`",
            f"- Delta: `{portal['artifacts']['delta_dir']}`",
            "",
        ]
    )
    write_text(args.output_dir / "PORTAL.md", portal_md)

    open_script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$dashboard = Resolve-Path '{args.dashboard_dir / 'index.html'}'",
            "Start-Process $dashboard",
            "",
            f"Write-Output 'Dashboard: {args.dashboard_dir / 'index.html'}'",
            f"Write-Output 'Completion report: {args.completion_report_dir / 'REPORT.md'}'",
            f"Write-Output 'Release verification: {args.release_verification_dir / 'REPORT.md'}'",
            f"Write-Output 'Master delivery: {args.master_delivery_dir}'",
            f"Write-Output 'Delivery pack: {args.delivery_pack_dir}'",
        ]
    )
    write_text(args.output_dir / "OPEN_PORTAL.ps1", open_script + "\n")
    print(f"wrote phase c portal -> {args.output_dir}")


if __name__ == "__main__":
    main()
