#!/usr/bin/env python3
"""Inspect a local version iteration history directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "kube-actuary.version-iteration-history-status.v1"
HISTORY_SCHEMA = "kube-actuary.version-iteration-history.v1"
WORKLIST_SCHEMA = "kube-actuary.version-worklist.v1"
DIFF_SCHEMA = "kube-actuary.version-iteration-diff.v1"


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"missing file: {path}")
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path}: {exc}")
        return {}


def inspect_run(history_dir: Path, run: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    run_id = str(run.get("runId", ""))
    relative_path = str(run.get("path", ""))
    run_dir = history_dir / relative_path
    worklist = load_json(run_dir / "worklist.json", errors)
    readme = run_dir / "README.md"
    versions_dir = run_dir / "versions"
    if not readme.is_file():
        errors.append(f"missing run README: {readme}")
    if not versions_dir.is_dir():
        errors.append(f"missing versions directory: {versions_dir}")
    if worklist.get("schemaVersion") != WORKLIST_SCHEMA:
        errors.append(f"run {run_id} worklist schema mismatch")

    missing_version_files = []
    for version in worklist.get("versions", []):
        if not isinstance(version, dict):
            continue
        slug = str(version.get("version", "")).lower().replace(".", "-")
        slug = "".join(character if character.isalnum() else "-" for character in slug).strip("-")
        for suffix in (".json", ".md"):
            path = versions_dir / f"{slug}{suffix}"
            if not path.is_file():
                missing_version_files.append(path.name)

    diff_status = "none"
    diff_summary = None
    diff_path = run.get("diffPath")
    if diff_path:
        diff = load_json(history_dir / str(diff_path), errors)
        if diff.get("schemaVersion") != DIFF_SCHEMA:
            errors.append(f"run {run_id} diff schema mismatch")
        else:
            diff_status = "present"
            diff_summary = diff.get("summary", {})

    if missing_version_files:
        errors.append(f"run {run_id} missing version files: {', '.join(sorted(missing_version_files))}")

    return {
        "runId": run_id,
        "path": relative_path,
        "worklistSchema": worklist.get("schemaVersion"),
        "summary": worklist.get("summary", {}),
        "diffStatus": diff_status,
        "diffSummary": diff_summary,
    }


def inspect_history(history_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    index = load_json(history_dir / "index.json", errors)
    if index.get("schemaVersion") != HISTORY_SCHEMA:
        errors.append("history index schema mismatch")
    runs = index.get("runs", [])
    if not isinstance(runs, list):
        errors.append("history index runs must be a list")
        runs = []
    readme = history_dir / "README.md"
    if not readme.is_file():
        errors.append(f"missing history README: {readme}")

    inspected_runs = [
        inspect_run(history_dir, run, errors)
        for run in runs
        if isinstance(run, dict)
    ]
    latest = inspected_runs[-1] if inspected_runs else None
    latest_summary = latest.get("summary", {}) if latest else {}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "historyDir": history_dir.as_posix(),
        "valid": not errors,
        "errors": errors,
        "summary": {
            "runs": len(inspected_runs),
            "latestRunId": latest.get("runId") if latest else None,
            "openItems": latest_summary.get("openItems", 0),
            "captureReady": latest_summary.get("captureReady", 0),
            "blockedByTools": latest_summary.get("blockedByTools", 0),
            "blockedByEnvironment": latest_summary.get("blockedByEnvironment", 0),
            "evidenceItems": latest_summary.get("evidenceItems", 0),
            "completeEvidenceItems": latest_summary.get("completeEvidenceItems", 0),
            "evidenceFiles": latest_summary.get("evidenceFiles", 0),
            "existingEvidenceFiles": latest_summary.get("existingEvidenceFiles", 0),
            "diffs": sum(1 for run in inspected_runs if run.get("diffStatus") == "present"),
        },
        "runs": inspected_runs,
    }


def render_text(status: dict[str, Any]) -> str:
    summary = status["summary"]
    state = "valid" if status["valid"] else "failed"
    lines = [
        f"version-iteration-history-status: {state}",
        f"runs: {summary['runs']}",
        f"latest-run-id: {summary['latestRunId']}",
        f"open-items: {summary['openItems']}",
        f"capture-ready: {summary['captureReady']}",
        f"blocked-by-tools: {summary['blockedByTools']}",
        f"blocked-by-environment: {summary['blockedByEnvironment']}",
        f"evidence-files: {summary['existingEvidenceFiles']}/{summary['evidenceFiles']}",
        f"complete-evidence-items: {summary['completeEvidenceItems']}/{summary['evidenceItems']}",
        f"diffs: {summary['diffs']}",
    ]
    for error in status["errors"]:
        lines.append(f"error: {error}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a KubeActuary version iteration history directory.")
    parser.add_argument("history_dir")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    status = inspect_history(Path(args.history_dir))
    rendered = (
        json.dumps(status, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else render_text(status)
    )
    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"version-iteration-history-status: wrote {args.output}")
    return 0 if status["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
