#!/usr/bin/env python3
"""Inspect local release evidence directory coverage without requiring closure."""

from __future__ import annotations

import argparse
import json
import shlex
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
NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"
NEXT_TASK_RUN_SCHEMA = "kube-actuary.next-version-task-run.v1"
ENVIRONMENT_PROBE_SCHEMA = "kube-actuary.environment-probe.v1"
ENVIRONMENT_BLOCKERS_SCHEMA = "kube-actuary.environment-blockers.v1"
NEXT_TASK_FILE_FLAGS = {
    "--sample": "sample",
    "--source": "source",
    "--output": "output",
}


def next_task_files(selected: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for command in selected.get("resolvedCommands", []):
        try:
            tokens = shlex.split(command)
        except ValueError:
            continue
        for index, token in enumerate(tokens[:-1]):
            role = NEXT_TASK_FILE_FLAGS.get(token)
            if role is None:
                continue
            path = tokens[index + 1]
            key = (role, path)
            if key in seen:
                continue
            seen.add(key)
            files.append(
                {
                    "role": role,
                    "path": path,
                    "exists": Path(path).is_file(),
                }
            )
    return files


def load_next_task(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "next-version-task.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_TASK_SCHEMA:
        raise ValueError(f"{path}: unsupported next-task schemaVersion: {payload.get('schemaVersion')!r}")
    selected = payload.get("selected") or {}
    files = next_task_files(selected)
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "summary": {
            "files": len(files),
            "existingFiles": sum(1 for item in files if item["exists"]),
            "missingFiles": sum(1 for item in files if not item["exists"]),
        },
        "selected": {
            "id": selected.get("id"),
            "version": selected.get("version"),
            "item": selected.get("item"),
            "kind": selected.get("kind"),
            "captureStatus": selected.get("captureStatus"),
            "environmentStatus": selected.get("environmentStatus"),
            "missingTools": selected.get("missingTools", []),
            "commands": selected.get("commands", []),
            "resolvedCommands": selected.get("resolvedCommands", []),
            "files": files,
        },
    }


def load_next_task_run(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "next-version-task-run.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_TASK_RUN_SCHEMA:
        raise ValueError(f"{path}: unsupported next-task-run schemaVersion: {payload.get('schemaVersion')!r}")
    next_task = payload.get("nextTask") or {}
    selected = next_task.get("selected") or {}
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "clusterWrites": payload.get("clusterWrites"),
        "ranAt": payload.get("ranAt"),
        "summary": payload.get("summary", {}),
        "selected": {
            "id": selected.get("id"),
            "version": selected.get("version"),
            "item": selected.get("item"),
            "kind": selected.get("kind"),
            "captureStatus": selected.get("captureStatus"),
        },
    }


def load_environment_probe(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "environment-probe.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != ENVIRONMENT_PROBE_SCHEMA:
        raise ValueError(f"{path}: unsupported environment-probe schemaVersion: {payload.get('schemaVersion')!r}")
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "clusterWrites": payload.get("clusterWrites"),
        "probeEnabled": payload.get("probeEnabled"),
        "clusterAccess": payload.get("clusterAccess"),
        "kubectl": payload.get("kubectl"),
        "summary": payload.get("summary", {}),
    }


def load_environment_blockers(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "environment-blockers.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != ENVIRONMENT_BLOCKERS_SCHEMA:
        raise ValueError(f"{path}: unsupported environment-blockers schemaVersion: {payload.get('schemaVersion')!r}")
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "clusterWrites": payload.get("clusterWrites"),
        "summary": payload.get("summary", {}),
        "selected": payload.get("selected"),
    }


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
    next_task = load_next_task(evidence_dir)
    next_task_run = load_next_task_run(evidence_dir)
    environment_probe = load_environment_probe(evidence_dir)
    environment_blockers = load_environment_blockers(evidence_dir)
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
        "nextTask": next_task,
        "nextTaskRun": next_task_run,
        "environmentProbe": environment_probe,
        "environmentBlockers": environment_blockers,
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
    next_task = status.get("nextTask")
    selected = next_task.get("selected", {}) if isinstance(next_task, dict) else {}
    if selected:
        lines.append(f"next-task: {selected.get('id')}")
        lines.append(f"next-task-status: {selected.get('captureStatus')}")
        file_summary = next_task.get("summary", {}) if isinstance(next_task, dict) else {}
        if file_summary:
            lines.append(
                f"next-task-files: {file_summary.get('existingFiles', 0)}/{file_summary.get('files', 0)}"
            )
        for item in selected.get("files", [])[:4]:
            file_status = "present" if item.get("exists") else "missing"
            lines.append(f"next-task-file: {file_status} {item.get('role')} {item.get('path')}")
        for command in selected.get("resolvedCommands", [])[:2]:
            lines.append(f"next-task-command: {command}")
    next_task_run = status.get("nextTaskRun")
    if isinstance(next_task_run, dict):
        lines.append(f"next-task-run: {next_task_run.get('status')}")
        lines.append(f"next-task-run-mode: {next_task_run.get('mode')}")
        run_summary = next_task_run.get("summary", {})
        if run_summary:
            lines.append(f"next-task-run-ran: {run_summary.get('ran', 0)}")
    environment_probe = status.get("environmentProbe")
    if isinstance(environment_probe, dict):
        lines.append(f"environment-probe: {environment_probe.get('clusterAccess')}")
        probe_summary = environment_probe.get("summary", {})
        if probe_summary:
            lines.append(f"environment-probe-checks: {probe_summary.get('passed', 0)}/{probe_summary.get('checks', 0)}")
    environment_blockers = status.get("environmentBlockers")
    if isinstance(environment_blockers, dict):
        blocker_summary = environment_blockers.get("summary", {})
        lines.append(f"environment-blockers: {blocker_summary.get('blockedByEnvironment', 0)}")
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
