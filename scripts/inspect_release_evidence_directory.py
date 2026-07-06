#!/usr/bin/env python3
"""Inspect local release evidence directory coverage without requiring closure."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_live_evidence_manifest import build_manifest  # noqa: E402
from scripts.build_release_evidence_directory import DEFAULT_OUTPUT_DIR, scan_directory  # noqa: E402
from scripts.check_live_evidence_coverage import check_coverage  # noqa: E402
from scripts.evaluate_external_gate_evidence import evaluate, load_supplemental  # noqa: E402


SCHEMA_VERSION = "kube-actuary.release-evidence-status.v1"


def unique_commands(gates: list[dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for gate in gates:
        for command in gate.get("recommendedCommands", []):
            if command not in seen:
                commands.append(command)
                seen.add(command)
    if "python3 -B scripts/build_release_evidence_directory.py <evidence-dir>" not in seen:
        commands.append("python3 -B scripts/build_release_evidence_directory.py <evidence-dir>")
    return commands


def inspect_directory(evidence_dir: Path, output_dir: Path) -> dict[str, Any]:
    if not evidence_dir.is_dir():
        raise ValueError(f"{evidence_dir}: evidence directory not found")
    live_reports, supplemental_paths, errors = scan_directory(evidence_dir, output_dir, require_live_reports=False)
    if errors:
        raise ValueError("; ".join(errors))

    manifest = build_manifest(live_reports)
    evaluation = evaluate(manifest, supplemental_paths)
    coverage_errors = check_coverage(manifest)
    supplemental = [load_supplemental(path) for path in supplemental_paths]
    uncovered = [gate for gate in evaluation.get("gates", []) if gate.get("covered") is not True]
    summary = evaluation.get("summary", {})
    complete = summary.get("uncovered") == 0 and not coverage_errors
    return {
        "schemaVersion": SCHEMA_VERSION,
        "evidenceDir": str(evidence_dir),
        "outputDir": str(output_dir),
        "summary": {
            "status": "complete" if complete else "partial",
            "liveReports": len(live_reports),
            "supplementalEvidence": len(supplemental_paths),
            "coveredGates": summary.get("covered", 0),
            "uncoveredGates": summary.get("uncovered", 0),
            "totalGates": summary.get("total", 0),
            "coverageErrors": len(coverage_errors),
        },
        "liveReports": manifest.get("reports", []),
        "supplementalEvidence": [
            {
                "path": str(path),
                "kind": record.get("kind"),
                "summary": record.get("summary"),
            }
            for path, record in zip(supplemental_paths, supplemental)
        ],
        "missing": {
            "coverage": coverage_errors,
            "externalGates": [
                {
                    "id": gate.get("id"),
                    "item": gate.get("item"),
                    "kind": gate.get("kind"),
                    "reason": gate.get("reason"),
                }
                for gate in uncovered
            ],
        },
        "nextCommands": unique_commands(uncovered),
    }


def render_text(status: dict[str, Any]) -> str:
    summary = status["summary"]
    lines = [
        f"release-evidence-status: {summary['status']}",
        f"live-reports: {summary['liveReports']}",
        f"supplemental: {summary['supplementalEvidence']}",
        f"covered: {summary['coveredGates']}/{summary['totalGates']}",
        f"coverage-errors: {summary['coverageErrors']}",
        f"next-commands: {len(status['nextCommands'])}",
    ]
    for command in status["nextCommands"][:5]:
        lines.append(f"next: {command}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect KubeActuary release evidence directory status.")
    parser.add_argument("evidence_dir", help="directory containing captured live and supplemental evidence JSON")
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"artifact output directory, default: <evidence-dir>/{DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    output_dir = Path(args.output_dir) if args.output_dir else evidence_dir / DEFAULT_OUTPUT_DIR
    try:
        status = inspect_directory(evidence_dir, output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("release-evidence-status: failed")
        print(f"error: {exc}")
        return 1

    if args.format == "json":
        rendered = json.dumps(status, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_text(status)

    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"release-evidence-status: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
