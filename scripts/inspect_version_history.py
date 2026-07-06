#!/usr/bin/env python3
"""Inspect a local version iteration history directory."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "kube-actuary.version-iteration-history-status.v1"
HISTORY_SCHEMA = "kube-actuary.version-iteration-history.v1"
WORKLIST_SCHEMA = "kube-actuary.version-worklist.v1"
DIFF_SCHEMA = "kube-actuary.version-iteration-diff.v1"
STATUS_JSON = "status.json"
STATUS_MD = "status.md"
DIFF_SUMMARY_KEYS = (
    "statusChanged",
    "openItemsDelta",
    "captureReadyDelta",
    "blockedByToolsDelta",
    "blockedByEnvironmentDelta",
    "existingEvidenceFilesDelta",
    "completeEvidenceItemsDelta",
    "changedItems",
    "addedItems",
    "removedItems",
)
VERSION_DELTA_KEYS = (
    "open",
    "captureReady",
    "blockedByTools",
    "blockedByEnvironment",
    "existingEvidenceFiles",
    "completeEvidenceItems",
)
FILTER_KEYS = (
    "versions",
    "openOnly",
    "captureStatuses",
    "missingTools",
    "environmentStatuses",
    "evidenceDir",
    "probeEnvironment",
    "kubectl",
)
NEXT_TASK_STATUS_PRIORITY = ("tool-ready", "blocked-by-environment", "missing-tools", "not-external-gate")


def shell_join(args: list[str]) -> str:
    return " ".join(shlex.quote(str(arg)) for arg in args)


def add_repeated_filter_args(args: list[str], flag: str, values: Any) -> None:
    if not isinstance(values, list):
        return
    for value in values:
        args.extend([flag, str(value)])


def dash_label(value: str) -> str:
    return "".join(f"-{character.lower()}" if character.isupper() else character for character in value)


def render_filter_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "none"
    return str(value)


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


def summarize_version_diff(version: dict[str, Any]) -> dict[str, Any]:
    summary_delta = version.get("summaryDelta", {})
    if not isinstance(summary_delta, dict):
        summary_delta = {}
    return {
        "version": version.get("version"),
        "beforeStatus": version.get("beforeStatus"),
        "afterStatus": version.get("afterStatus"),
        "statusChanged": version.get("statusChanged"),
        "summaryDelta": {
            key: summary_delta.get(key, 0)
            for key in VERSION_DELTA_KEYS
        },
        "changedItems": version.get("changedItems", []) if isinstance(version.get("changedItems"), list) else [],
        "addedItems": version.get("addedItems", []) if isinstance(version.get("addedItems"), list) else [],
        "removedItems": version.get("removedItems", []) if isinstance(version.get("removedItems"), list) else [],
    }


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def selected_worklist_commands(selected: dict[str, Any], evidence_dir: Path | None = None) -> list[str]:
    args = [
        "python3",
        "-B",
        "scripts/generate_version_worklist.py",
        "--format",
        "markdown",
        "--open-only",
    ]
    if evidence_dir is not None:
        args.extend(["--evidence-dir", evidence_dir.as_posix()])
    if selected.get("version"):
        args.extend(["--version", str(selected["version"])])
    capture_status = selected.get("captureStatus")
    if capture_status:
        args.extend(["--capture-status", str(capture_status)])
    if capture_status == "missing-tools" and selected.get("missingTools"):
        return [
            shell_join([*args, "--missing-tool", str(tool)])
            for tool in selected.get("missingTools", [])
        ]
    if capture_status == "blocked-by-environment" and selected.get("environmentStatus"):
        args.extend(["--environment-status", str(selected["environmentStatus"])])
    return [shell_join(args)]


def summarize_task(version: dict[str, Any], item: dict[str, Any], version_index: int, item_index: int) -> dict[str, Any]:
    result = {
        "version": version.get("version"),
        "versionStatus": version.get("status"),
        "versionIndex": version_index,
        "itemIndex": item_index,
        "id": item.get("id"),
        "item": item.get("item"),
        "status": item.get("status"),
        "captureStatus": item.get("captureStatus"),
        "kind": item.get("kind"),
        "environmentStatus": item.get("environmentStatus"),
        "missingTools": list_value(item.get("missingTools")),
        "nextStep": item.get("nextStep"),
        "evidenceSummary": dict_value(item.get("evidenceSummary")),
        "files": list_value(item.get("files")),
        "commands": list_value(item.get("commands")),
        "resolvedCommands": list_value(item.get("resolvedCommands")),
    }
    evidence_dir = item.get("evidenceDir")
    if evidence_dir:
        result["evidenceDir"] = evidence_dir
    result["worklistCommands"] = selected_worklist_commands(
        result,
        Path(str(evidence_dir)) if evidence_dir else None,
    )
    return result


def summarize_next_task(worklist: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for version_index, version in enumerate(worklist.get("versions", []), start=1):
        if not isinstance(version, dict):
            continue
        for item_index, item in enumerate(version.get("openItems", []), start=1):
            if isinstance(item, dict):
                candidates.append(summarize_task(version, item, version_index, item_index))
    for status in NEXT_TASK_STATUS_PRIORITY:
        for candidate in candidates:
            if candidate.get("captureStatus") == status:
                return candidate
    return candidates[0] if candidates else None


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
    diff_versions: list[dict[str, Any]] = []
    diff_path = run.get("diffPath")
    if diff_path:
        diff = load_json(history_dir / str(diff_path), errors)
        if diff.get("schemaVersion") != DIFF_SCHEMA:
            errors.append(f"run {run_id} diff schema mismatch")
        else:
            diff_status = "present"
            diff_summary = diff.get("summary", {})
            diff_versions = [
                summarize_version_diff(version)
                for version in diff.get("versions", [])
                if isinstance(version, dict)
            ]

    if missing_version_files:
        errors.append(f"run {run_id} missing version files: {', '.join(sorted(missing_version_files))}")

    blockers = worklist.get("blockers", {})
    return {
        "runId": run_id,
        "path": relative_path,
        "diffPath": str(diff_path) if diff_path else None,
        "worklistSchema": worklist.get("schemaVersion"),
        "queueSource": run.get("queueSource") or worklist.get("queueSource") or "generated",
        "summary": worklist.get("summary", {}),
        "blockers": blockers if isinstance(blockers, dict) else {},
        "environmentProbe": summarize_environment_probe(worklist.get("environmentProbe")),
        "nextTask": summarize_next_task(worklist),
        "filters": run.get("filters", {}) if isinstance(run.get("filters"), dict) else {},
        "diffStatus": diff_status,
        "diffSummary": diff_summary,
        "diffVersions": diff_versions,
    }


def build_next_commands(history_dir: Path, latest: dict[str, Any] | None) -> list[str]:
    commands = [
        shell_join(
            [
                "python3",
                "-B",
                "scripts/inspect_version_history.py",
                history_dir.as_posix(),
                "--record",
            ]
        )
    ]
    if not latest:
        return commands
    filters = latest.get("filters", {}) if isinstance(latest.get("filters"), dict) else {}
    evidence_dir = filters.get("evidenceDir")
    probe_environment = filters.get("probeEnvironment") is True
    kubectl = str(filters.get("kubectl") or "kubectl")
    if evidence_dir:
        args = [
            "python3",
            "-B",
            "scripts/advance_version_iteration.py",
            str(evidence_dir),
            history_dir.as_posix(),
        ]
        if probe_environment:
            args.append("--probe-environment")
        if kubectl != "kubectl":
            args.extend(["--kubectl", kubectl])
        add_repeated_filter_args(args, "--capture-status", filters.get("captureStatuses"))
        add_repeated_filter_args(args, "--missing-tool", filters.get("missingTools"))
        add_repeated_filter_args(args, "--environment-status", filters.get("environmentStatuses"))
        args.append("--run")
    else:
        args = [
            "python3",
            "-B",
            "scripts/record_version_iteration.py",
            history_dir.as_posix(),
        ]
        add_repeated_filter_args(args, "--version", filters.get("versions"))
        if filters.get("openOnly") is True:
            args.append("--open-only")
        add_repeated_filter_args(args, "--capture-status", filters.get("captureStatuses"))
        add_repeated_filter_args(args, "--missing-tool", filters.get("missingTools"))
        add_repeated_filter_args(args, "--environment-status", filters.get("environmentStatuses"))
        if probe_environment:
            args.append("--probe-environment")
        if kubectl != "kubectl":
            args.extend(["--kubectl", kubectl])
    commands.append(shell_join(args))
    return commands


def build_latest_artifacts(history_dir: Path, latest: dict[str, Any] | None) -> dict[str, str]:
    if not latest:
        return {}
    relative_path = latest.get("path")
    if not relative_path:
        return {}
    run_path = history_dir / str(relative_path)
    artifacts = {
        "runPath": run_path.as_posix(),
        "worklistPath": (run_path / "worklist.json").as_posix(),
    }
    diff_path = latest.get("diffPath")
    if diff_path:
        artifacts["diffPath"] = (history_dir / str(diff_path)).as_posix()
    return artifacts


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
    latest_next_task = latest.get("nextTask") if latest else None
    if not isinstance(latest_next_task, dict):
        latest_next_task = None
    latest_filters = latest.get("filters", {}) if latest else {}
    if not isinstance(latest_filters, dict):
        latest_filters = {}
    latest_diff_summary = latest.get("diffSummary", {}) if latest else {}
    if not isinstance(latest_diff_summary, dict):
        latest_diff_summary = {}
    latest_version_diffs = latest.get("diffVersions", []) if latest else []
    if not isinstance(latest_version_diffs, list):
        latest_version_diffs = []
    latest_artifacts = build_latest_artifacts(history_dir, latest)
    next_commands = build_next_commands(history_dir, latest)
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
        "latestNextTask": latest_next_task,
        "latestFilters": latest_filters,
        "latestDiffSummary": latest_diff_summary,
        "latestVersionDiffs": latest_version_diffs,
        "latestArtifacts": latest_artifacts,
        "nextCommands": next_commands,
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
    latest_diff = status.get("latestDiffSummary", {})
    if isinstance(latest_diff, dict) and latest_diff:
        for key in DIFF_SUMMARY_KEYS:
            if key in latest_diff:
                lines.append(f"latest-diff-{dash_label(key)}: {latest_diff[key]}")
    latest_artifacts = status.get("latestArtifacts", {})
    if isinstance(latest_artifacts, dict) and latest_artifacts:
        for key in ("runPath", "worklistPath", "diffPath"):
            if key in latest_artifacts:
                lines.append(f"latest-artifact-{dash_label(key)}: {latest_artifacts[key]}")
    latest_filters = status.get("latestFilters", {})
    if isinstance(latest_filters, dict) and latest_filters:
        for key in FILTER_KEYS:
            if key in latest_filters:
                lines.append(f"latest-filter-{dash_label(key)}: {render_filter_value(latest_filters[key])}")
    latest_next_task = status.get("latestNextTask")
    if isinstance(latest_next_task, dict):
        lines.extend(
            [
                f"latest-next-task-version: {latest_next_task.get('version')}",
                f"latest-next-task-id: {latest_next_task.get('id')}",
                f"latest-next-task-item: {latest_next_task.get('item')}",
                f"latest-next-task-capture-status: {latest_next_task.get('captureStatus')}",
                f"latest-next-task-kind: {latest_next_task.get('kind')}",
            ]
        )
        if latest_next_task.get("environmentStatus"):
            lines.append(f"latest-next-task-environment-status: {latest_next_task['environmentStatus']}")
        if latest_next_task.get("missingTools"):
            lines.append(f"latest-next-task-missing-tools: {', '.join(str(tool) for tool in latest_next_task['missingTools'])}")
        if latest_next_task.get("nextStep"):
            lines.append(f"latest-next-task-next-step: {latest_next_task['nextStep']}")
        evidence = dict_value(latest_next_task.get("evidenceSummary"))
        if evidence:
            lines.append(f"latest-next-task-evidence-files: {evidence.get('existingFiles', 0)}/{evidence.get('files', 0)}")
        for file_item in list_value(latest_next_task.get("files")):
            if not isinstance(file_item, dict):
                continue
            exists = "yes" if file_item.get("exists") is True else "no"
            lines.append(
                f"latest-next-task-file: {file_item.get('role')} "
                f"{file_item.get('path')} exists={exists}"
            )
        commands = list_value(latest_next_task.get("resolvedCommands")) or list_value(latest_next_task.get("commands"))
        for command in commands:
            lines.append(f"latest-next-task-command: {command}")
        for command in list_value(latest_next_task.get("worklistCommands")):
            lines.append(f"latest-next-task-worklist: {command}")
    for version in status.get("latestVersionDiffs", []) or []:
        if not isinstance(version, dict):
            continue
        delta = version.get("summaryDelta", {}) if isinstance(version.get("summaryDelta"), dict) else {}
        lines.append(
            f"latest-version-diff: {version.get('version')} "
            f"{version.get('beforeStatus')}->{version.get('afterStatus')} "
            f"capture-ready-delta={delta.get('captureReady', 0)} "
            f"blocked-by-environment-delta={delta.get('blockedByEnvironment', 0)} "
            f"changed-items={len(version.get('changedItems', []) or [])}"
        )
    for command in status.get("nextCommands", []):
        lines.append(f"next-command: {command}")
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
        "## Latest Artifacts",
        "",
    ]
    latest_artifacts = status.get("latestArtifacts", {})
    if isinstance(latest_artifacts, dict) and latest_artifacts:
        for key in ("runPath", "worklistPath", "diffPath"):
            if key in latest_artifacts:
                lines.append(f"- {dash_label(key)}: `{latest_artifacts[key]}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Latest Filters",
            "",
        ]
    )
    latest_filters = status.get("latestFilters", {})
    if isinstance(latest_filters, dict) and latest_filters:
        for key in FILTER_KEYS:
            if key in latest_filters:
                lines.append(f"- {dash_label(key)}: `{render_filter_value(latest_filters[key])}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Latest Next Task",
            "",
        ]
    )
    latest_next_task = status.get("latestNextTask")
    if isinstance(latest_next_task, dict):
        lines.append(
            f"- `{latest_next_task.get('captureStatus')}` {latest_next_task.get('item')} "
            f"({latest_next_task.get('version')})"
        )
        lines.append(f"  - id: `{latest_next_task.get('id')}`")
        if latest_next_task.get("kind"):
            lines.append(f"  - kind: `{latest_next_task.get('kind')}`")
        if latest_next_task.get("environmentStatus"):
            lines.append(f"  - environment: `{latest_next_task['environmentStatus']}`")
        if latest_next_task.get("missingTools"):
            lines.append(f"  - missing tools: `{', '.join(str(tool) for tool in latest_next_task['missingTools'])}`")
        if latest_next_task.get("nextStep"):
            lines.append(f"  - next: {latest_next_task['nextStep']}")
        evidence = dict_value(latest_next_task.get("evidenceSummary"))
        if evidence:
            lines.append(f"  - evidence files: `{evidence.get('existingFiles', 0)}/{evidence.get('files', 0)}`")
        for file_item in list_value(latest_next_task.get("files")):
            if not isinstance(file_item, dict):
                continue
            exists = "yes" if file_item.get("exists") is True else "no"
            lines.append(
                f"  - file `{file_item.get('role')}` "
                f"`{file_item.get('path')}` exists=`{exists}`"
            )
        commands = list_value(latest_next_task.get("resolvedCommands")) or list_value(latest_next_task.get("commands"))
        for command in commands:
            lines.append(f"  - `{command}`")
        for command in list_value(latest_next_task.get("worklistCommands")):
            lines.append(f"  - worklist: `{command}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Latest Diff",
            "",
        ]
    )
    latest_diff = status.get("latestDiffSummary", {})
    if isinstance(latest_diff, dict) and latest_diff:
        for key in DIFF_SUMMARY_KEYS:
            if key in latest_diff:
                lines.append(f"- {dash_label(key)}: {latest_diff[key]}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Latest Version Diffs",
            "",
        ]
    )
    version_diffs = status.get("latestVersionDiffs", [])
    if version_diffs:
        for version in version_diffs:
            if not isinstance(version, dict):
                continue
            delta = version.get("summaryDelta", {}) if isinstance(version.get("summaryDelta"), dict) else {}
            lines.append(
                f"- `{version.get('version')}` {version.get('beforeStatus')} -> {version.get('afterStatus')} "
                f"capture-ready-delta={delta.get('captureReady', 0)} "
                f"blocked-by-environment-delta={delta.get('blockedByEnvironment', 0)} "
                f"changed-items={len(version.get('changedItems', []) or [])}"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Commands",
            "",
        ]
    )
    next_commands = status.get("nextCommands", [])
    if next_commands:
        for command in next_commands:
            lines.append(f"- `{command}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Latest Blockers",
            "",
        ]
    )
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
