from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_REQUEST_ROOT = Path("scratch/phase_c_model_request_batches_v1")
DEFAULT_RESPONSE_ROOT = Path("scratch/phase_c_model_responses_v1")
DEFAULT_INGEST_ROOT = Path("scratch/phase_c_model_response_ingest_v1")
DEFAULT_MERGE_PLAN_DIR = Path("scratch/phase_c_model_merge_plan_v1")
DEFAULT_PHASE_C_JSON = Path("scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2/all_segments.json")
DEFAULT_PHASE_C_POINTER = Path("scratch/PHASE_C_CURRENT_MODEL_APPLIED.txt")
DEFAULT_APPLIED_OUTPUT_DIR = Path("scratch/phase_c_model_applied_v1")
DEFAULT_DELTA_OUTPUT_DIR = Path("scratch/phase_c_model_delta_pack_v1")
DEFAULT_BURNIN_OUTPUT_DIR = Path("scratch/phase_c_burnin_prep_v1")
DEFAULT_PARTS_ROOT = Path("scratch")
DEFAULT_NEXT_RETRY_OUTPUT_DIR = Path("scratch/phase_c_model_retry_batches_v1")
DEFAULT_HANDOFF_OUTPUT_DIR = Path("scratch/phase_c_model_handoff_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Phase C model postprocess: ingest responses, build merge plan, apply back to all_segments."
    )
    parser.add_argument("--request-root", type=Path, default=DEFAULT_REQUEST_ROOT)
    parser.add_argument("--response-root", type=Path, default=DEFAULT_RESPONSE_ROOT)
    parser.add_argument("--ingest-root", type=Path, default=DEFAULT_INGEST_ROOT)
    parser.add_argument("--merge-plan-dir", type=Path, default=DEFAULT_MERGE_PLAN_DIR)
    parser.add_argument("--phase-c-json", type=Path)
    parser.add_argument("--applied-output-dir", type=Path, default=DEFAULT_APPLIED_OUTPUT_DIR)
    parser.add_argument("--delta-output-dir", type=Path, default=DEFAULT_DELTA_OUTPUT_DIR)
    parser.add_argument("--burnin-output-dir", type=Path, default=DEFAULT_BURNIN_OUTPUT_DIR)
    parser.add_argument("--parts-root", type=Path, default=DEFAULT_PARTS_ROOT)
    parser.add_argument("--handoff-output-dir", type=Path, default=DEFAULT_HANDOFF_OUTPUT_DIR)
    parser.add_argument("--update-current-pointers", action="store_true")
    parser.add_argument("--next-retry-output-dir", type=Path, help="Optional output dir for auto-building the next retry queue after postprocess.")
    parser.add_argument("--next-retry-output-queue-name", type=str, help="Optional explicit next retry queue name, e.g. retry_round2.")
    parser.add_argument("--next-retry-confidence-threshold", type=float, default=0.6)
    parser.add_argument("--next-retry-skip-missing", action="store_true")
    parser.add_argument(
        "--queue-names",
        nargs="+",
        help="Optional subset of queues. If omitted, auto-detect queues from response-root.",
    )
    return parser.parse_args()


def run_command(args: list[str]) -> None:
    print(">>", " ".join(args))
    subprocess.run(args, check=True)


def ensure_response_dir(response_root: Path, queue_name: str) -> Path:
    queue_dir = response_root / queue_name
    if not queue_dir.exists():
        raise SystemExit(f"missing response directory for queue '{queue_name}': {queue_dir}")
    jsonl_files = sorted(queue_dir.glob("*.jsonl"))
    if not jsonl_files:
        raise SystemExit(f"no response jsonl files found for queue '{queue_name}': {queue_dir}")
    return queue_dir


def resolve_queue_names(args: argparse.Namespace) -> list[str]:
    if args.queue_names:
        return list(args.queue_names)

    detected: list[str] = []
    for queue_dir in sorted(path for path in args.response_root.iterdir() if path.is_dir()):
        if any(queue_dir.glob("*.jsonl")) and (args.request_root / queue_dir.name / "manifest.json").exists():
            detected.append(queue_dir.name)
    if not detected:
        raise SystemExit(f"no queue response dirs with jsonl files found under: {args.response_root}")
    return detected


def resolve_phase_c_json(phase_c_json: Path | None) -> Path:
    if phase_c_json is not None:
        return phase_c_json
    if DEFAULT_PHASE_C_POINTER.exists():
        pointer_text = DEFAULT_PHASE_C_POINTER.read_text(encoding="utf-8").strip()
        if pointer_text:
            pointer_path = Path(pointer_text)
            candidate = pointer_path / "all_segments.json" if pointer_path.is_dir() else pointer_path
            if candidate.exists():
                return candidate
    return DEFAULT_PHASE_C_JSON


def main() -> None:
    args = parse_args()
    python_exe = sys.executable
    queue_names = resolve_queue_names(args)
    phase_c_json = resolve_phase_c_json(args.phase_c_json)

    for queue_name in queue_names:
        response_dir = ensure_response_dir(args.response_root, queue_name)
        run_command(
            [
                python_exe,
                "tools/ingest_phase_c_model_responses.py",
                "--request-root",
                str(args.request_root),
                "--queue-name",
                queue_name,
                "--response-dir",
                str(response_dir),
                "--output-dir",
                str(args.ingest_root),
            ]
        )

    run_command(
        [
            python_exe,
            "tools/build_phase_c_model_merge_plan.py",
            "--ingest-root",
            str(args.ingest_root),
            "--queue-names",
            *queue_names,
            "--output-dir",
            str(args.merge_plan_dir),
        ]
    )

    run_command(
        [
            python_exe,
            "tools/apply_phase_c_model_merge_plan.py",
            "--phase-c-json",
            str(phase_c_json),
            "--merge-plan-tsv",
            str(args.merge_plan_dir / "actions.tsv"),
            "--output-dir",
            str(args.applied_output_dir),
            *(
                ["--update-current-pointer"]
                if args.update_current_pointers
                else []
            ),
        ]
    )

    run_command(
        [
            python_exe,
            "tools/build_phase_c_model_delta_pack.py",
            "--base-json",
            str(phase_c_json),
            "--applied-json",
            str(args.applied_output_dir / "all_segments.json"),
            "--output-dir",
            str(args.delta_output_dir),
        ]
    )

    run_command(
        [
            python_exe,
            "tools/export_phase_c_burnin_prep.py",
            "--phase-c-dir",
            str(args.applied_output_dir),
            "--parts-root",
            str(args.parts_root),
            "--output-dir",
            str(args.burnin_output_dir),
        ]
    )

    if args.next_retry_output_dir:
        retry_command = [
            python_exe,
            "tools/build_phase_c_model_retry_batches.py",
            "--request-root",
            str(args.request_root),
            "--ingest-root",
            str(args.ingest_root),
            "--output-dir",
            str(args.next_retry_output_dir),
            "--confidence-threshold",
            str(args.next_retry_confidence_threshold),
            "--queue-names",
            *queue_names,
        ]
        if args.next_retry_output_queue_name:
            retry_command.extend(["--output-queue-name", args.next_retry_output_queue_name])
        if args.next_retry_skip_missing:
            retry_command.append("--skip-missing")
        if args.update_current_pointers:
            retry_command.append("--update-current-pointer")
        run_command(retry_command)

    run_command(
        [
            python_exe,
            "tools/build_phase_c_model_handoff.py",
            "--request-root",
            str(args.request_root),
            "--queue-names",
            *queue_names,
            "--ingest-root",
            str(args.ingest_root),
            "--merge-plan-dir",
            str(args.merge_plan_dir),
            "--applied-output-dir",
            str(args.applied_output_dir),
            "--delta-output-dir",
            str(args.delta_output_dir),
            "--burnin-output-dir",
            str(args.burnin_output_dir),
            "--output-dir",
            str(args.handoff_output_dir),
            *(
                ["--update-current-pointers"]
                if args.update_current_pointers
                else []
            ),
            *(
                ["--next-retry-output-dir", str(args.next_retry_output_dir)]
                if args.next_retry_output_dir
                else []
            ),
        ]
    )

    print(f"wrote final applied output -> {args.applied_output_dir}")


if __name__ == "__main__":
    main()
