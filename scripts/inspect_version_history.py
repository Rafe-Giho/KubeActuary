#!/usr/bin/env python3
"""Inspect a local version iteration history directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "kube-actuary.version-iteration-history-status.v1"
HISTORY_SCHEMA = "kube-actuary.version-iteration-history.v1"
WORKLIST_SCHEMA = "kube-actuary.version-worklist.v1"
DIFF_SCHEMA = "kube-actuary.version-iteration-diff.v1"
STATUS_JSON = "status.json"
STATUS_MD = "status.md"


def probe_message(check: dict[str, Any]) -> str | None:
    for key in ("stderr", "stdout"):
        value = check.get(key)
        if not isinstance(value, str):
            continue
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if lines:
            return lines[-1]
    return None


def summarize_environment_probe(probe: Any) -> dict[str, Any]:
    if not isinstance(probe, dict) or not probe:
        return {}
    checks = probe.get("checks", [])
    failed_checks = []
    if isinstance(checks, list):
        for check in checks:
            if not isinstance(check, dict) or check.get("ok") is True:
                continue
            failed_checks.append(
                {
                    "name": check.get("name"),
                    "exitCode": check.get("exitCode"),
                    "message": probe_message(check),
                }
            )
    return {
        "enabled": probe.get("enabled"),
        "kubectl": probe.get("kubectl"),
        "clusterAccess": probe.get("clusterAccess"),
        "failedChecks": failed_checks,
    }


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

    blockers = worklist.get("blockers", {})
    return {
        "runId": run_id,
        "path": relative_path,
        "worklistSchema": worklist.get("schemaVersion"),
        "queueSource": run.get("queueSource") or worklist.get("queueSource") or "generated",
        "summary": worklist.get("summary", {}),
        "blockers": blockers if isinstance(blockers, dict) else {},
        "environmentProbe": summarize_environment_probe(worklist.get("environmentProbe")),
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
    latest_blockers = latest.get("blockers", {}) if latest else {}
    latest_environment_probe = latest.get("environmentProbe", {}) if latest else {}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "historyDir": history_dir.as_posix(),
        "valid": not errors,
        "errors": errors,
        "summary": {
            "runs": len(inspected_runs),
            "latestRunId": latest.get("runId") if latest else None,
            "latestQueueSource": latest.get("queueSource") if latest else None,
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
        "latestBlockers": latest_blockers,
        "latestEnvironmentProbe": latest_environment_probe,
        "runs": inspected_runs,
    }


def render_text(status: dict[str, Any]) -> str:
    summary = status["summary"]
    state = "valid" if status["valid"] else "failed"
    lines = [
        f"version-iteration-history-status: {state}",
        f"runs: {summary['runs']}",
        f"latest-run-id: {summary['latestRunId']}",
        f"latest-queue-source: {summary.get('latestQueueSource')}",
        f"open-items: {summary['openItems']}",
        f"capture-ready: {summary['captureReady']}",
        f"blocked-by-tools: {summary['blockedByTools']}",
        f"blocked-by-environment: {summary['blockedByEnvironment']}",
        f"evidence-files: {summary['existingEvidenceFiles']}/{summary['evidenceFiles']}",
        f"complete-evidence-items: {summary['completeEvidenceItems']}/{summary['evidenceItems']}",
        f"diffs: {summary['diffs']}",
    ]
    blockers = status.get("latestBlockers", {})
    if isinstance(blockers, dict):
        for item in blockers.get("missingTools", []) or []:
            lines.append(f"missing-tool-blocker: {item.get('tool')} ({item.get('items')} items)")
            if item.get("worklistCommand"):
                lines.append(f"missing-tool-worklist: {item.get('worklistCommand')}")
        for item in blockers.get("environment", []) or []:
            lines.append(f"environment-blocker: {item.get('status')} ({item.get('items')} items)")
            if item.get("worklistCommand"):
                lines.append(f"environment-worklist: {item.get('worklistCommand')}")
        for item in blockers.get("environmentNextSteps", []) or []:
            lines.append(f"blocker-next-step: {item.get('nextStep')} ({item.get('items')} items)")
    environment_probe = status.get("latestEnvironmentProbe", {})
    if isinstance(environment_probe, dict) and environment_probe:
        lines.append(f"environment-probe: {environment_probe.get('clusterAccess')}")
        if environment_probe.get("kubectl"):
            lines.append(f"environment-probe-kubectl: {environment_probe.get('kubectl')}")
        for check in environment_probe.get("failedChecks", []) or []:
            message = check.get("message")
            suffix = f" message={message}" if message else ""
            lines.append(
                f"environment-probe-failure: {check.get('name')} "
                f"exit={check.get('exitCode')}{suffix}"
            )
    for error in status["errors"]:
        lines.append(f"error: {error}")
    return "\n".join(lines) + "\n"


def render_markdown(status: dict[str, Any]) -> str:
    summary = status["summary"]
    state = "valid" if status["valid"] else "failed"
    lines = [
        "# KubeActuary Version Iteration History Status",
        "",
        f"Schema: `{status['schemaVersion']}`",
        f"Status: `{state}`",
        f"History directory: `{status['historyDir']}`",
        "",
        "## Summary",
        "",
        f"- runs: {summary['runs']}",
        f"- latest run: `{summary['latestRunId']}`",
        f"- latest queue source: `{summary.get('latestQueueSource')}`",
        f"- open items: {summary['openItems']}",
        f"- capture ready: {summary['captureReady']}",
        f"- blocked by tools: {summary['blockedByTools']}",
        f"- blocked by environment: {summary['blockedByEnvironment']}",
        f"- evidence files: {summary['existingEvidenceFiles']}/{summary['evidenceFiles']}",
        f"- complete evidence items: {summary['completeEvidenceItems']}/{summary['evidenceItems']}",
        f"- diffs: {summary['diffs']}",
        "",
        "## Latest Blockers",
        "",
    ]
    blockers = status.get("latestBlockers", {})
    if not isinstance(blockers, dict) or not any(blockers.values()):
        lines.append("- none")
    else:
        for item in blockers.get("missingTools", []) or []:
            lines.append(f"- missing tool `{item.get('tool')}`: {item.get('items')} items")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item.get('worklistCommand')}`")
        for item in blockers.get("environment", []) or []:
            lines.append(f"- environment `{item.get('status')}`: {item.get('items')} items")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item.get('worklistCommand')}`")
        for item in blockers.get("environmentNextSteps", []) or []:
            lines.append(f"- next step: {item.get('nextStep')} ({item.get('items')} items)")
    environment_probe = status.get("latestEnvironmentProbe", {})
    if isinstance(environment_probe, dict) and environment_probe:
        lines.extend(["", "## Latest Environment Probe", ""])
        lines.append(f"- cluster access: `{environment_probe.get('clusterAccess')}`")
        if environment_probe.get("kubectl"):
            lines.append(f"- kubectl: `{environment_probe.get('kubectl')}`")
        failed_checks = environment_probe.get("failedChecks", []) or []
        if not failed_checks:
            lines.append("- failed checks: none")
        for check in failed_checks:
            message = f": {check.get('message')}" if check.get("message") else ""
            lines.append(
                f"- failed `{check.get('name')}` exit={check.get('exitCode')}{message}"
            )
    if status["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in status["errors"]:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def record_status(history_dir: Path, status: dict[str, Any]) -> dict[str, str]:
    json_path = history_dir / STATUS_JSON
    markdown_path = history_dir / STATUS_MD
    record = {"json": str(json_path), "markdown": str(markdown_path)}
    history_dir.mkdir(parents=True, exist_ok=True)
    status["record"] = record
    json_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_markdown(status))
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a KubeActuary version iteration history directory.")
    parser.add_argument("history_dir")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--record", action="store_true", help="write status JSON and Markdown into the history directory")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    history_dir = Path(args.history_dir)
    status = inspect_history(history_dir)
    recorded = record_status(history_dir, status) if args.record else None
    if args.format == "json":
        rendered = json.dumps(status, indent=2, sort_keys=True) + "\n"
    elif args.format == "markdown":
        rendered = render_markdown(status)
    else:
        rendered = render_text(status)
    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"version-iteration-history-status: wrote {args.output}")
    if recorded:
        print(f"version-iteration-history-status: recorded {recorded['json']}", file=sys.stderr)
    return 0 if status["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
