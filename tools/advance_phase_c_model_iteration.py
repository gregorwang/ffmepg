from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_REQUEST_POINTER = Path("scratch/PHASE_C_CURRENT_MODEL_REQUESTS.txt")
DEFAULT_PHASE_C_JSON = Path("scratch/phase_c_fulltrack_rebuild_v5b_cliplocal_offline_qc2/all_segments.json")
DEFAULT_PHASE_C_POINTER = Path("scratch/PHASE_C_CURRENT_MODEL_APPLIED.txt")
DEFAULT_OUTPUT_ROOT = Path("scratch/phase_c_model_iterations_v1")
DEFAULT_PARTS_ROOT = Path("scratch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Advance one Phase C model iteration using the current request pointer.")
    parser.add_argument("--request-pointer", type=Path, default=DEFAULT_REQUEST_POINTER)
    parser.add_argument("--response-root", type=Path, required=True)
    parser.add_argument("--phase-c-json", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--parts-root", type=Path, default=DEFAULT_PARTS_ROOT)
    parser.add_argument("--next-retry-skip-missing", action="store_true")
    parser.add_argument("--next-retry-confidence-threshold", type=float, default=0.6)
    parser.add_argument("--update-current-pointers", action="store_true")
    return parser.parse_args()


def read_request_pointer(path: Path) -> tuple[Path, str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 2:
        raise SystemExit(f"invalid request pointer format in: {path}")
    return Path(lines[0]), lines[1]


def next_round_dir(output_root: Path, queue_name: str) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    max_no = 0
    pattern = re.compile(r"round_(\d{3})_")
    for child in output_root.iterdir():
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if match:
            max_no = max(max_no, int(match.group(1)))
    safe_queue = re.sub(r"[^A-Za-z0-9._-]+", "_", queue_name)
    return output_root / f"round_{max_no + 1:03d}_{safe_queue}"


def run_command(args: list[str]) -> None:
    print(">>", " ".join(args))
    subprocess.run(args, check=True)


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
    request_root, queue_name = read_request_pointer(args.request_pointer)
    round_dir = next_round_dir(args.output_root, queue_name)
    phase_c_json = resolve_phase_c_json(args.phase_c_json)

    run_command(
        [
            python_exe,
            "tools/run_phase_c_model_postprocess.py",
            "--request-root",
            str(request_root),
            "--response-root",
            str(args.response_root),
            "--queue-names",
            queue_name,
            "--ingest-root",
            str(round_dir / "ingest"),
            "--merge-plan-dir",
            str(round_dir / "merge"),
            "--phase-c-json",
            str(phase_c_json),
            "--applied-output-dir",
            str(round_dir / "applied"),
            "--delta-output-dir",
            str(round_dir / "delta"),
            "--burnin-output-dir",
            str(round_dir / "burnin"),
            "--handoff-output-dir",
            str(round_dir / "handoff"),
            "--parts-root",
            str(args.parts_root),
            *(
                ["--update-current-pointers"]
                if args.update_current_pointers
                else []
            ),
            "--next-retry-output-dir",
            str(round_dir / "next_retry"),
            "--next-retry-confidence-threshold",
            str(args.next_retry_confidence_threshold),
            *(
                ["--next-retry-skip-missing"]
                if args.next_retry_skip_missing
                else []
            ),
        ]
    )

    print(f"wrote phase c iteration -> {round_dir}")


if __name__ == "__main__":
    main()
