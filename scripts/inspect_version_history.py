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
ADVANCE_SCHEMA = "kube-actuary.version-iteration-advance.v1"
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
    "environmentReasons",
    "evidenceDir",
    "probeEnvironment",
    "kubectl",
)
NEXT_TASK_STATUS_PRIORITY = ("tool-ready", "blocked-by-environment", "missing-tools", "not-external-gate")
BLOCKER_CAPTURE_STATUSES = ("blocked-by-environment", "missing-tools")


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
                    "reason": check.get("reason"),
                    "message": probe_message(check),
                }
            )
    return {
        "enabled": probe.get("enabled"),
        "kubectl": probe.get("kubectl"),
        "clusterAccess": probe.get("clusterAccess"),
        "reason": probe.get("reason"),
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
    if capture_status == "blocked-by-environment" and selected.get("environmentReason"):
        args.extend(["--environment-reason", str(selected["environmentReason"])])
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
        "environmentReason": item.get("environmentReason"),
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
    next_unblock_action = dict_value(worklist.get("nextUnblockAction")) or dict_value(run.get("nextUnblockAction"))
    next_unblock_action_run = dict_value(worklist.get("nextUnblockActionRun")) or dict_value(
        run.get("nextUnblockActionRun")
    )
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
        "nextUnblockAction": next_unblock_action or None,
        "nextUnblockActionRun": next_unblock_action_run or None,
        "filters": run.get("filters", {}) if isinstance(run.get("filters"), dict) else {},
        "diffStatus": diff_status,
        "diffSummary": diff_summary,
        "diffVersions": diff_versions,
    }


def summarize_latest_advance(latest: dict[str, Any] | None, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(latest, dict):
        return None
    filters = latest.get("filters", {}) if isinstance(latest.get("filters"), dict) else {}
    evidence_dir = filters.get("evidenceDir")
    if not evidence_dir:
        return None
    path = Path(str(evidence_dir)) / ".kubeactuary" / "version-iteration-advance.json"
    if not path.is_file():
        return None
    payload = load_json(path, errors)
    if payload.get("schemaVersion") != ADVANCE_SCHEMA:
        errors.append(f"{path}: advance schema mismatch")
    runner = payload.get("runner", {}) if isinstance(payload.get("runner"), dict) else {}
    next_task = payload.get("nextTask", {}) if isinstance(payload.get("nextTask"), dict) else {}
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": path.as_posix(),
        "status": payload.get("status"),
        "mode": payload.get("mode"),
        "runId": payload.get("runId"),
        "createdAt": payload.get("createdAt"),
        "queueSource": payload.get("queueSource"),
        "runnerStatus": runner.get("status"),
        "runnerMode": runner.get("mode"),
        "runnerSummary": runner.get("summary", {}) if isinstance(runner.get("summary"), dict) else {},
        "nextTask": {
            "selected": next_task.get("selected"),
            "captureStatus": next_task.get("captureStatus"),
            "environmentStatus": next_task.get("environmentStatus"),
            "environmentReason": next_task.get("environmentReason"),
            "missingTools": list_value(next_task.get("missingTools")),
            "nextStep": next_task.get("nextStep"),
            "skippedCompleteEvidence": next_task.get("skippedCompleteEvidence"),
            "worklistCommands": list_value(next_task.get("worklistCommands")),
        },
    }


def latest_advance_next_task_consistency(
    latest_next_task: dict[str, Any] | None,
    latest_advance: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(latest_next_task, dict) or not isinstance(latest_advance, dict):
        return None
    advance_next_task = latest_advance.get("nextTask", {})
    if not isinstance(advance_next_task, dict):
        return None
    latest_id = latest_next_task.get("id")
    advance_id = advance_next_task.get("selected")
    comparisons = [
        ("selected", advance_id, latest_id),
        ("captureStatus", advance_next_task.get("captureStatus"), latest_next_task.get("captureStatus")),
        ("environmentStatus", advance_next_task.get("environmentStatus"), latest_next_task.get("environmentStatus")),
        ("environmentReason", advance_next_task.get("environmentReason"), latest_next_task.get("environmentReason")),
        ("nextStep", advance_next_task.get("nextStep"), latest_next_task.get("nextStep")),
    ]
    mismatches = [
        field
        for field, advance_value, latest_value in comparisons
        if advance_value != latest_value
    ]
    return {
        "status": "mismatched" if mismatches else "matched",
        "mismatches": mismatches,
        "advanceSelected": advance_id,
        "latestSelected": latest_id,
    }


def blocker_signature(run: dict[str, Any]) -> dict[str, Any] | None:
    next_task = run.get("nextTask")
    if not isinstance(next_task, dict):
        return None
    capture_status = next_task.get("captureStatus")
    if capture_status not in BLOCKER_CAPTURE_STATUSES:
        return None
    missing_tools = sorted(str(tool) for tool in list_value(next_task.get("missingTools")))
    return {
        "id": next_task.get("id"),
        "version": next_task.get("version"),
        "kind": next_task.get("kind"),
        "captureStatus": capture_status,
        "environmentStatus": next_task.get("environmentStatus"),
        "environmentReason": next_task.get("environmentReason"),
        "missingTools": missing_tools,
        "nextStep": next_task.get("nextStep"),
    }


def latest_blocker_streak(inspected_runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not inspected_runs:
        return None
    signature = blocker_signature(inspected_runs[-1])
    if signature is None:
        return None
    matching: list[dict[str, Any]] = []
    for run in reversed(inspected_runs):
        if blocker_signature(run) != signature:
            break
        matching.append(run)
    matching.reverse()
    run_ids = [run.get("runId") for run in matching]
    return {
        "status": "repeated" if len(matching) > 1 else "single",
        "streak": len(matching),
        "firstRunId": run_ids[0] if run_ids else None,
        "latestRunId": run_ids[-1] if run_ids else None,
        "runIds": run_ids,
        "signature": signature,
    }


def latest_blocker_action(
    blocker_streak: dict[str, Any] | None,
    latest_next_task: dict[str, Any] | None,
    next_commands: list[str],
) -> dict[str, Any] | None:
    if not isinstance(blocker_streak, dict):
        return None
    signature = blocker_streak.get("signature", {})
    if not isinstance(signature, dict):
        return None
    capture_status = signature.get("captureStatus")
    if capture_status == "blocked-by-environment":
        action = "resolve-environment"
        retry_after = "environment probe succeeds"
        default_next_step = "start or select a disposable cluster, then rerun the probe"
    elif capture_status == "missing-tools":
        action = "install-missing-tools"
        retry_after = "required local tools are installed"
        default_next_step = "install missing tools or run on a host that has them"
    else:
        return None
    worklist_commands = []
    if isinstance(latest_next_task, dict):
        worklist_commands = list_value(latest_next_task.get("worklistCommands"))
    retry_command = next(
        (command for command in next_commands if "scripts/advance_version_iteration.py" in command),
        None,
    )
    if retry_command is None and len(next_commands) > 1:
        retry_command = next_commands[-1]
    return {
        "action": action,
        "captureStatus": capture_status,
        "repeated": blocker_streak.get("status") == "repeated",
        "streak": blocker_streak.get("streak"),
        "retryRecommended": False,
        "retryAfter": retry_after,
        "nextStep": signature.get("nextStep") or default_next_step,
        "reason": signature.get("environmentReason") or ", ".join(signature.get("missingTools", [])),
        "worklistCommands": worklist_commands,
        "retryCommand": retry_command,
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
        add_repeated_filter_args(args, "--version", filters.get("versions"))
        if probe_environment:
            args.append("--probe-environment")
        if kubectl != "kubectl":
            args.extend(["--kubectl", kubectl])
        add_repeated_filter_args(args, "--capture-status", filters.get("captureStatuses"))
        add_repeated_filter_args(args, "--missing-tool", filters.get("missingTools"))
        add_repeated_filter_args(args, "--environment-status", filters.get("environmentStatuses"))
        add_repeated_filter_args(args, "--environment-reason", filters.get("environmentReasons"))
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
        add_repeated_filter_args(args, "--environment-reason", filters.get("environmentReasons"))
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
    latest_next_unblock_action = latest.get("nextUnblockAction") if latest else None
    if not isinstance(latest_next_unblock_action, dict):
        latest_next_unblock_action = None
    latest_next_unblock_action_run = latest.get("nextUnblockActionRun") if latest else None
    if not isinstance(latest_next_unblock_action_run, dict):
        latest_next_unblock_action_run = None
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
    latest_advance = summarize_latest_advance(latest, errors)
    if isinstance(latest_advance, dict):
        latest_advance["nextTaskConsistency"] = latest_advance_next_task_consistency(
            latest_next_task,
            latest_advance,
        )
    blocker_streak = latest_blocker_streak(inspected_runs)
    next_commands = build_next_commands(history_dir, latest)
    blocker_action = latest_blocker_action(blocker_streak, latest_next_task, next_commands)
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
        "latestNextUnblockAction": latest_next_unblock_action,
        "latestNextUnblockActionRun": latest_next_unblock_action_run,
        "latestFilters": latest_filters,
        "latestDiffSummary": latest_diff_summary,
        "latestVersionDiffs": latest_version_diffs,
        "latestArtifacts": latest_artifacts,
        "latestAdvance": latest_advance,
        "latestBlockerStreak": blocker_streak,
        "latestBlockerAction": blocker_action,
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
        if latest_next_task.get("environmentReason"):
            lines.append(f"latest-next-task-environment-reason: {latest_next_task['environmentReason']}")
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
    latest_next_unblock_action = status.get("latestNextUnblockAction")
    if isinstance(latest_next_unblock_action, dict):
        selected = dict_value(latest_next_unblock_action.get("selected"))
        lines.append(f"latest-next-unblock-action: {selected.get('id')}")
        lines.append(f"latest-next-unblock-action-status: {latest_next_unblock_action.get('status')}")
        if latest_next_unblock_action.get("queueSource"):
            lines.append(f"latest-next-unblock-action-queue-source: {latest_next_unblock_action.get('queueSource')}")
        if selected.get("kind"):
            lines.append(f"latest-next-unblock-action-kind: {selected.get('kind')}")
        if selected.get("target"):
            lines.append(f"latest-next-unblock-action-target: {selected.get('target')}")
        if selected.get("items") is not None:
            lines.append(f"latest-next-unblock-action-items: {selected.get('items')}")
        if selected.get("nextStep"):
            lines.append(f"latest-next-unblock-action-next-step: {selected.get('nextStep')}")
        commands = dict_value(selected.get("commands"))
        for command in list_value(commands.get("verify")):
            lines.append(f"latest-next-unblock-action-verify: {command}")
    latest_next_unblock_action_run = status.get("latestNextUnblockActionRun")
    if isinstance(latest_next_unblock_action_run, dict):
        summary = dict_value(latest_next_unblock_action_run.get("summary"))
        lines.append(f"latest-next-unblock-run: {latest_next_unblock_action_run.get('status')}")
        lines.append(f"latest-next-unblock-run-mode: {latest_next_unblock_action_run.get('mode')}")
        if latest_next_unblock_action_run.get("queueSource"):
            lines.append(f"latest-next-unblock-run-queue-source: {latest_next_unblock_action_run.get('queueSource')}")
        if summary:
            lines.append(
                "latest-next-unblock-run-ran: "
                f"{summary.get('ran', 0)}/{summary.get('commands', 0)}"
            )
            lines.append(f"latest-next-unblock-run-failed: {summary.get('failed', 0)}")
        failure = dict_value(latest_next_unblock_action_run.get("failure"))
        if failure.get("message"):
            lines.append(f"latest-next-unblock-run-error: {failure.get('message')}")
    latest_blocker = status.get("latestBlockerStreak")
    if isinstance(latest_blocker, dict):
        signature = latest_blocker.get("signature", {})
        if not isinstance(signature, dict):
            signature = {}
        lines.append(f"latest-blocker-streak: {latest_blocker.get('streak')}")
        lines.append(f"latest-blocker-status: {latest_blocker.get('status')}")
        lines.append(f"latest-blocker-first-run-id: {latest_blocker.get('firstRunId')}")
        lines.append(f"latest-blocker-latest-run-id: {latest_blocker.get('latestRunId')}")
        lines.append(f"latest-blocker-id: {signature.get('id')}")
        lines.append(f"latest-blocker-capture-status: {signature.get('captureStatus')}")
        if signature.get("environmentStatus"):
            lines.append(f"latest-blocker-environment-status: {signature.get('environmentStatus')}")
        if signature.get("environmentReason"):
            lines.append(f"latest-blocker-environment-reason: {signature.get('environmentReason')}")
        if signature.get("missingTools"):
            lines.append(f"latest-blocker-missing-tools: {', '.join(str(tool) for tool in signature.get('missingTools', []))}")
    blocker_action = status.get("latestBlockerAction")
    if isinstance(blocker_action, dict):
        lines.append(f"latest-blocker-action: {blocker_action.get('action')}")
        lines.append(f"latest-blocker-retry-recommended: {str(blocker_action.get('retryRecommended')).lower()}")
        lines.append(f"latest-blocker-retry-after: {blocker_action.get('retryAfter')}")
        if blocker_action.get("reason"):
            lines.append(f"latest-blocker-action-reason: {blocker_action.get('reason')}")
        if blocker_action.get("nextStep"):
            lines.append(f"latest-blocker-action-next-step: {blocker_action.get('nextStep')}")
        for command in list_value(blocker_action.get("worklistCommands")):
            lines.append(f"latest-blocker-action-worklist: {command}")
        if blocker_action.get("retryCommand"):
            lines.append(f"latest-blocker-action-retry-command: {blocker_action.get('retryCommand')}")
    latest_advance = status.get("latestAdvance")
    if isinstance(latest_advance, dict):
        lines.append(f"latest-advance-status: {latest_advance.get('status')}")
        lines.append(f"latest-advance-mode: {latest_advance.get('mode')}")
        if latest_advance.get("runId"):
            lines.append(f"latest-advance-run-id: {latest_advance.get('runId')}")
        if latest_advance.get("queueSource"):
            lines.append(f"latest-advance-queue-source: {latest_advance.get('queueSource')}")
        if latest_advance.get("path"):
            lines.append(f"latest-advance-path: {latest_advance.get('path')}")
        if latest_advance.get("runnerStatus"):
            lines.append(f"latest-advance-runner-status: {latest_advance.get('runnerStatus')}")
        runner_summary = latest_advance.get("runnerSummary", {})
        if isinstance(runner_summary, dict) and runner_summary:
            lines.append(
                "latest-advance-runner-ran: "
                f"{runner_summary.get('ran', 0)}/{runner_summary.get('commands', 0)}"
            )
        advance_next_task = latest_advance.get("nextTask", {})
        if isinstance(advance_next_task, dict) and advance_next_task:
            if advance_next_task.get("selected"):
                lines.append(f"latest-advance-next-task: {advance_next_task.get('selected')}")
            if advance_next_task.get("captureStatus"):
                lines.append(f"latest-advance-next-task-status: {advance_next_task.get('captureStatus')}")
            if advance_next_task.get("environmentStatus"):
                lines.append(f"latest-advance-next-task-environment-status: {advance_next_task.get('environmentStatus')}")
            if advance_next_task.get("environmentReason"):
                lines.append(f"latest-advance-next-task-environment-reason: {advance_next_task.get('environmentReason')}")
            if advance_next_task.get("nextStep"):
                lines.append(f"latest-advance-next-task-next-step: {advance_next_task.get('nextStep')}")
            if advance_next_task.get("skippedCompleteEvidence") is not None:
                lines.append(f"latest-advance-skipped-complete-evidence: {advance_next_task.get('skippedCompleteEvidence')}")
            for command in list_value(advance_next_task.get("worklistCommands")):
                lines.append(f"latest-advance-next-task-worklist: {command}")
        consistency = latest_advance.get("nextTaskConsistency")
        if isinstance(consistency, dict):
            lines.append(f"latest-advance-next-task-consistency: {consistency.get('status')}")
            if consistency.get("mismatches"):
                lines.append(f"latest-advance-next-task-mismatches: {', '.join(consistency.get('mismatches', []))}")
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
        for item in blockers.get("environmentReasons", []) or []:
            lines.append(f"environment-reason-blocker: {item.get('reason')} ({item.get('items')} items)")
            if item.get("worklistCommand"):
                lines.append(f"environment-reason-worklist: {item.get('worklistCommand')}")
        for item in blockers.get("environmentNextSteps", []) or []:
            lines.append(f"blocker-next-step: {item.get('nextStep')} ({item.get('items')} items)")
    environment_probe = status.get("latestEnvironmentProbe", {})
    if isinstance(environment_probe, dict) and environment_probe:
        lines.append(f"environment-probe: {environment_probe.get('clusterAccess')}")
        if environment_probe.get("reason"):
            lines.append(f"environment-probe-reason: {environment_probe.get('reason')}")
        if environment_probe.get("kubectl"):
            lines.append(f"environment-probe-kubectl: {environment_probe.get('kubectl')}")
        for check in environment_probe.get("failedChecks", []) or []:
            message = check.get("message")
            suffix = f" message={message}" if message else ""
            reason = f" reason={check.get('reason')}" if check.get("reason") else ""
            lines.append(
                f"environment-probe-failure: {check.get('name')} "
                f"exit={check.get('exitCode')}{reason}{suffix}"
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
        if latest_next_task.get("environmentReason"):
            lines.append(f"  - environment reason: `{latest_next_task['environmentReason']}`")
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
            "## Latest Next Unblock",
            "",
        ]
    )
    latest_next_unblock_action = status.get("latestNextUnblockAction")
    latest_next_unblock_action_run = status.get("latestNextUnblockActionRun")
    if isinstance(latest_next_unblock_action, dict):
        selected = dict_value(latest_next_unblock_action.get("selected"))
        lines.append(f"- action: `{selected.get('id')}`")
        lines.append(f"- status: `{latest_next_unblock_action.get('status')}`")
        if latest_next_unblock_action.get("queueSource"):
            lines.append(f"- queue source: `{latest_next_unblock_action.get('queueSource')}`")
        if selected.get("kind"):
            lines.append(f"- kind: `{selected.get('kind')}`")
        if selected.get("target"):
            lines.append(f"- target: `{selected.get('target')}`")
        if selected.get("items") is not None:
            lines.append(f"- items: {selected.get('items')}")
        if selected.get("nextStep"):
            lines.append(f"- next step: {selected.get('nextStep')}")
        commands = dict_value(selected.get("commands"))
        for command in list_value(commands.get("verify")):
            lines.append(f"- verify: `{command}`")
    else:
        lines.append("- action: none")
    if isinstance(latest_next_unblock_action_run, dict):
        summary = dict_value(latest_next_unblock_action_run.get("summary"))
        lines.append(f"- run: `{latest_next_unblock_action_run.get('status')}`")
        lines.append(f"- run mode: `{latest_next_unblock_action_run.get('mode')}`")
        if summary:
            lines.append(
                f"- run commands: `{summary.get('ran', 0)}/{summary.get('commands', 0)}` "
                f"failed={summary.get('failed', 0)}"
            )
        failure = dict_value(latest_next_unblock_action_run.get("failure"))
        if failure.get("message"):
            lines.append(f"- run blocker: `{failure.get('message')}`")
    else:
        lines.append("- run: none")
    latest_blocker = status.get("latestBlockerStreak")
    lines.extend(
        [
            "",
            "## Latest Blocker Streak",
            "",
        ]
    )
    if isinstance(latest_blocker, dict):
        signature = latest_blocker.get("signature", {})
        if not isinstance(signature, dict):
            signature = {}
        lines.append(
            f"- `{latest_blocker.get('status')}` streak={latest_blocker.get('streak')} "
            f"latest=`{latest_blocker.get('latestRunId')}`"
        )
        lines.append(f"- first run: `{latest_blocker.get('firstRunId')}`")
        lines.append(f"- blocked task: `{signature.get('id')}`")
        lines.append(f"- capture status: `{signature.get('captureStatus')}`")
        if signature.get("environmentStatus"):
            lines.append(f"- environment: `{signature.get('environmentStatus')}`")
        if signature.get("environmentReason"):
            lines.append(f"- environment reason: `{signature.get('environmentReason')}`")
        if signature.get("missingTools"):
            lines.append(f"- missing tools: `{', '.join(str(tool) for tool in signature.get('missingTools', []))}`")
    else:
        lines.append("- none")
    blocker_action = status.get("latestBlockerAction")
    lines.extend(
        [
            "",
            "## Latest Blocker Action",
            "",
        ]
    )
    if isinstance(blocker_action, dict):
        lines.append(f"- action: `{blocker_action.get('action')}`")
        lines.append(f"- retry recommended: `{str(blocker_action.get('retryRecommended')).lower()}`")
        lines.append(f"- retry after: {blocker_action.get('retryAfter')}")
        if blocker_action.get("reason"):
            lines.append(f"- reason: `{blocker_action.get('reason')}`")
        if blocker_action.get("nextStep"):
            lines.append(f"- next step: {blocker_action.get('nextStep')}")
        for command in list_value(blocker_action.get("worklistCommands")):
            lines.append(f"- worklist: `{command}`")
        if blocker_action.get("retryCommand"):
            lines.append(f"- retry command: `{blocker_action.get('retryCommand')}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Latest Advance",
            "",
        ]
    )
    latest_advance = status.get("latestAdvance")
    if isinstance(latest_advance, dict):
        lines.append(f"- status: `{latest_advance.get('status')}`")
        lines.append(f"- mode: `{latest_advance.get('mode')}`")
        if latest_advance.get("runId"):
            lines.append(f"- run id: `{latest_advance.get('runId')}`")
        if latest_advance.get("queueSource"):
            lines.append(f"- queue source: `{latest_advance.get('queueSource')}`")
        if latest_advance.get("path"):
            lines.append(f"- path: `{latest_advance.get('path')}`")
        if latest_advance.get("runnerStatus"):
            lines.append(f"- runner: `{latest_advance.get('runnerStatus')}`")
        runner_summary = latest_advance.get("runnerSummary", {})
        if isinstance(runner_summary, dict) and runner_summary:
            lines.append(f"- runner ran: `{runner_summary.get('ran', 0)}/{runner_summary.get('commands', 0)}`")
        advance_next_task = latest_advance.get("nextTask", {})
        if isinstance(advance_next_task, dict) and advance_next_task:
            if advance_next_task.get("selected"):
                lines.append(f"- next task: `{advance_next_task.get('selected')}`")
            if advance_next_task.get("captureStatus"):
                lines.append(f"- next task status: `{advance_next_task.get('captureStatus')}`")
            if advance_next_task.get("environmentStatus"):
                lines.append(f"- next task environment: `{advance_next_task.get('environmentStatus')}`")
            if advance_next_task.get("environmentReason"):
                lines.append(f"- next task environment reason: `{advance_next_task.get('environmentReason')}`")
            if advance_next_task.get("nextStep"):
                lines.append(f"- next task next step: {advance_next_task.get('nextStep')}")
            if advance_next_task.get("skippedCompleteEvidence") is not None:
                lines.append(f"- skipped complete evidence: {advance_next_task.get('skippedCompleteEvidence')}")
            for command in list_value(advance_next_task.get("worklistCommands")):
                lines.append(f"- next task worklist: `{command}`")
        consistency = latest_advance.get("nextTaskConsistency")
        if isinstance(consistency, dict):
            lines.append(f"- next task consistency: `{consistency.get('status')}`")
            if consistency.get("mismatches"):
                lines.append(f"- next task mismatches: `{', '.join(consistency.get('mismatches', []))}`")
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
        for item in blockers.get("environmentReasons", []) or []:
            lines.append(f"- environment reason `{item.get('reason')}`: {item.get('items')} items")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item.get('worklistCommand')}`")
        for item in blockers.get("environmentNextSteps", []) or []:
            lines.append(f"- next step: {item.get('nextStep')} ({item.get('items')} items)")
    environment_probe = status.get("latestEnvironmentProbe", {})
    if isinstance(environment_probe, dict) and environment_probe:
        lines.extend(["", "## Latest Environment Probe", ""])
        lines.append(f"- cluster access: `{environment_probe.get('clusterAccess')}`")
        if environment_probe.get("reason"):
            lines.append(f"- reason: `{environment_probe.get('reason')}`")
        if environment_probe.get("kubectl"):
            lines.append(f"- kubectl: `{environment_probe.get('kubectl')}`")
        failed_checks = environment_probe.get("failedChecks", []) or []
        if not failed_checks:
            lines.append("- failed checks: none")
        for check in failed_checks:
            reason = f" reason={check.get('reason')}" if check.get("reason") else ""
            message = f": {check.get('message')}" if check.get("message") else ""
            lines.append(
                f"- failed `{check.get('name')}` exit={check.get('exitCode')}{reason}{message}"
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
