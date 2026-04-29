from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


DEFAULT_COMPLETION_REPORT_DIR = Path("scratch/phase_c_completion_report_v1_complete")
DEFAULT_RELEASE_VERIFICATION_DIR = Path("scratch/phase_c_release_verification_v1_complete")
DEFAULT_RELEASE_SNAPSHOT_DIR = Path("scratch/phase_c_release_snapshot_v1_complete")
DEFAULT_MASTER_DELIVERY_DIR = Path("scratch/phase_c_master_delivery_v1_complete")
DEFAULT_DELIVERY_PACK_DIR = Path("scratch/phase_c_delivery_pack_v1_complete")
DEFAULT_OUTPUT_DIR = Path("scratch/phase_c_dashboard_v1_complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a static HTML dashboard for the completed Phase C deliverable.")
    parser.add_argument("--completion-report-dir", type=Path, default=DEFAULT_COMPLETION_REPORT_DIR)
    parser.add_argument("--release-verification-dir", type=Path, default=DEFAULT_RELEASE_VERIFICATION_DIR)
    parser.add_argument("--release-snapshot-dir", type=Path, default=DEFAULT_RELEASE_SNAPSHOT_DIR)
    parser.add_argument("--master-delivery-dir", type=Path, default=DEFAULT_MASTER_DELIVERY_DIR)
    parser.add_argument("--delivery-pack-dir", type=Path, default=DEFAULT_DELIVERY_PACK_DIR)
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


def rel_link(base_dir: Path, target: Path) -> str:
    return target.resolve().relative_to(base_dir.resolve().anchor).as_posix() if False else Path(
        Path("..") / target.relative_to(base_dir.parent)
    ).as_posix()


def escape(text: Any) -> str:
    return html.escape(str(text))


def link_item(base_dir: Path, label: str, target: Path) -> str:
    relative = rel_link(base_dir, target)
    return f'<a href="{escape(relative)}">{escape(label)}</a>'


def stat_card(label: str, value: Any, note: str = "") -> str:
    note_html = f'<div class="note">{escape(note)}</div>' if note else ""
    return f'<div class="card"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div>{note_html}</div>'


def main() -> None:
    args = parse_args()
    completion_manifest = load_json(args.completion_report_dir / "manifest.json")
    completion_report = load_json(args.completion_report_dir / "report.json")
    verification_manifest = load_json(args.release_verification_dir / "manifest.json")
    release_snapshot_manifest = load_json(args.release_snapshot_dir / "manifest.json")
    master_manifest = load_json(args.master_delivery_dir / "manifest.json")
    delivery_manifest = load_json(args.delivery_pack_dir / "manifest.json")

    dashboard = {
        "completion_manifest": completion_manifest,
        "completion_report": completion_report,
        "verification_manifest": verification_manifest,
        "release_snapshot_manifest": release_snapshot_manifest,
        "master_manifest": master_manifest,
        "delivery_manifest": delivery_manifest,
    }
    write_json(args.output_dir / "dashboard.json", dashboard)

    base_dir = args.output_dir
    part_rows = []
    for row in delivery_manifest.get("part_stats") or []:
        part_rows.append(
            "<tr>"
            f"<td>{escape(row['short_name'])}</td>"
            f"<td>{escape(row['segment_count'])}</td>"
            f"<td>{escape(row['matched_count'])}</td>"
            f"<td>{escape(row['unmatched_count'])}</td>"
            f"<td>{escape(row['coverage_ratio'])}</td>"
            "</tr>"
        )

    artifact_rows = [
        ("Completion Report", args.completion_report_dir / "REPORT.md"),
        ("Completion Report JSON", args.completion_report_dir / "report.json"),
        ("Release Verification", args.release_verification_dir / "REPORT.md"),
        ("Release Verification JSON", args.release_verification_dir / "verification.json"),
        ("Release Snapshot Manifest", args.release_snapshot_dir / "manifest.json"),
        ("Master Delivery Manifest", args.master_delivery_dir / "manifest.json"),
        ("Delivery Pack Manifest", args.delivery_pack_dir / "manifest.json"),
        ("Matched Segments TSV", args.delivery_pack_dir / "matched_segments.tsv"),
        ("Unmatched Segments TSV", args.delivery_pack_dir / "unmatched_segments.tsv"),
    ]
    artifact_list = "\n".join(
        f"<li>{link_item(base_dir, label, target)}</li>" for label, target in artifact_rows
    )

    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Ghost Yotei Phase C Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      --bg: #f5f1e8;
      --panel: #fffaf0;
      --ink: #1d1b18;
      --muted: #6b6258;
      --line: #d8cdbd;
      --accent: #a33a2b;
      --accent-2: #2f5d50;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(163,58,43,0.08), transparent 28%),
        radial-gradient(circle at top right, rgba(47,93,80,0.08), transparent 26%),
        linear-gradient(180deg, #f7f2e8, var(--bg));
    }}
    .wrap {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 28px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 24px;
      border-radius: 18px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.05);
    }}
    h1, h2 {{
      margin: 0 0 12px 0;
      font-weight: 700;
      letter-spacing: 0.02em;
    }}
    p {{
      margin: 0;
      line-height: 1.6;
      color: var(--muted);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
      margin-top: 20px;
    }}
    .card {{
      background: rgba(255,255,255,0.65);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
    }}
    .label {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}
    .value {{
      font-size: 28px;
      margin-top: 8px;
      color: var(--accent);
    }}
    .note {{
      margin-top: 6px;
      font-size: 13px;
      color: var(--muted);
    }}
    .section {{
      margin-top: 20px;
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 22px;
      border-radius: 18px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.05);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-size: 14px;
    }}
    th {{
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-size: 11px;
    }}
    ul {{
      margin: 10px 0 0 18px;
      padding: 0;
    }}
    li {{
      margin: 8px 0;
      color: var(--muted);
    }}
    a {{
      color: var(--accent-2);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .footer {{
      margin-top: 18px;
      font-size: 13px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>Ghost Yotei Phase C Dashboard</h1>
      <p>Current completed Phase C deliverable after deterministic closure of the full review pool. This dashboard is an inspection layer, not a second source of truth.</p>
      <div class="grid">
        {stat_card("Total Cues", completion_manifest["total_cue_count"])}
        {stat_card("Matched", completion_manifest["matched_cue_count"], "Current Chinese text retained")}
        {stat_card("Unmatched", completion_manifest["unmatched_cue_count"], "Closed as no-match")}
        {stat_card("Coverage", completion_manifest["coverage_ratio"])}
        {stat_card("Model Requests Left", completion_manifest["remaining_model_requests"], "Pipeline complete")}
        {stat_card("Verification", verification_manifest["verification_status"], f"{verification_manifest['ok_count']} / {verification_manifest['artifact_count']} artifacts ok")}
      </div>
    </div>

    <div class="section">
      <h2>Closure</h2>
      <div class="grid">
        {stat_card("Keep Current Match", release_snapshot_manifest["decision_counts"]["keep_current_match"])}
        {stat_card("Reject Current Match", release_snapshot_manifest["decision_counts"]["reject_current_match"])}
        {stat_card("No Match", release_snapshot_manifest["decision_counts"]["no_match"])}
        {stat_card("Changed Vs Base", release_snapshot_manifest["changed_row_count_vs_base"])}
      </div>
      <div class="footer">The original model-review pool is fully closed. There is no remaining external model work in the current branch.</div>
    </div>

    <div class="section">
      <h2>Part Coverage</h2>
      <table>
        <thead>
          <tr><th>Part</th><th>Total</th><th>Matched</th><th>Unmatched</th><th>Coverage</th></tr>
        </thead>
        <tbody>
          {''.join(part_rows)}
        </tbody>
      </table>
    </div>

    <div class="section">
      <h2>Entry Points</h2>
      <ul>
        {artifact_list}
      </ul>
    </div>
  </div>
</body>
</html>
"""
    write_text(args.output_dir / "index.html", html_text)
    print(f"wrote phase c dashboard -> {args.output_dir}")


if __name__ == "__main__":
    main()
