#!/usr/bin/env python3
"""Inspect local release evidence directory coverage without requiring closure."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_live_evidence_manifest import build_manifest  # noqa: E402
from scripts.build_release_evidence_directory import DEFAULT_OUTPUT_DIR, scan_directory  # noqa: E402
from scripts.check_live_evidence_coverage import check_coverage  # noqa: E402
from scripts.evaluate_external_gate_evidence import evaluate, load_supplemental  # noqa: E402


SCHEMA_VERSION = "kube-actuary.release-evidence-status.v1"
STATUS_REPORT_JSON = "release-evidence-status.json"
STATUS_REPORT_MD = "release-evidence-status.md"
NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"
NEXT_TASK_BUILD_SCHEMA = "kube-actuary.next-task-evidence-build.v1"
NEXT_TASK_RUN_SCHEMA = "kube-actuary.next-version-task-run.v1"
NEXT_UNBLOCK_ACTION_SCHEMA = "kube-actuary.next-unblock-action.v1"
NEXT_UNBLOCK_ACTION_RUN_SCHEMA = "kube-actuary.next-unblock-action-run.v1"
ENVIRONMENT_PROBE_SCHEMA = "kube-actuary.environment-probe.v1"
ENVIRONMENT_BLOCKERS_SCHEMA = "kube-actuary.environment-blockers.v1"
ADVANCE_SCHEMA = "kube-actuary.version-iteration-advance.v1"
LIVE_QUEUE_SCHEMA = "kube-actuary.live-validation-queue.v1"
NEXT_TASK_FILE_FLAGS = {
    "--sample": "sample",
    "--source": "source",
    "--output": "output",
}
SELECTED_METADATA_FIELDS = (
    "environmentStatus",
    "environmentReason",
    "missingTools",
    "nextStep",
)


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


def fill_selected_metadata(record: dict[str, Any] | None, next_task: dict[str, Any] | None) -> None:
    if not isinstance(record, dict) or not isinstance(next_task, dict):
        return
    selected = record.get("selected")
    current = next_task.get("selected")
    if not isinstance(selected, dict) or not isinstance(current, dict):
        return
    if selected.get("id") != current.get("id"):
        return
    for field in SELECTED_METADATA_FIELDS:
        if selected.get(field) in (None, "", []):
            value = current.get(field)
            if value not in (None, "", []):
                selected[field] = value


def default_queue_source(live_queue: dict[str, Any] | None) -> tuple[str, str]:
    if isinstance(live_queue, dict):
        return "prepared-live-validation-queue", "inferred-live-validation-queue"
    return "generated", "default-generated"


def resolved_queue_source(payload: dict[str, Any], fallback: str, fallback_origin: str) -> tuple[str, str]:
    next_task = payload.get("nextTask") if isinstance(payload.get("nextTask"), dict) else {}
    if payload.get("sourceWorklistQueueSource"):
        return str(payload["sourceWorklistQueueSource"]), "explicit-source-worklist"
    if payload.get("queueSource"):
        return str(payload["queueSource"]), "explicit-record"
    if next_task.get("queueSource"):
        return str(next_task["queueSource"]), "explicit-next-task"
    return fallback, fallback_origin


def load_next_task(
    evidence_dir: Path,
    fallback_queue_source: str = "generated",
    fallback_queue_source_origin: str = "default-generated",
) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "next-version-task.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_TASK_SCHEMA:
        raise ValueError(f"{path}: unsupported next-task schemaVersion: {payload.get('schemaVersion')!r}")
    selected = payload.get("selected") or {}
    files = next_task_files(selected)
    queue_source, queue_source_origin = resolved_queue_source(
        payload,
        fallback_queue_source,
        fallback_queue_source_origin,
    )
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "queueSource": queue_source,
        "queueSourceOrigin": queue_source_origin,
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
            "environmentReason": selected.get("environmentReason"),
            "missingTools": selected.get("missingTools", []),
            "nextStep": selected.get("nextStep"),
            "commands": selected.get("commands", []),
            "resolvedCommands": selected.get("resolvedCommands", []),
            "files": files,
        },
    }


def failure_message(record: dict[str, Any]) -> str | None:
    lines: list[str] = []
    for key in ("stderr", "stdout"):
        value = record.get(key)
        if isinstance(value, str):
            lines.extend(line.strip() for line in value.splitlines() if line.strip())
    for line in lines:
        if line.lower().startswith("error:"):
            return line
    return lines[-1] if lines else None


def next_task_run_failure(payload: dict[str, Any]) -> dict[str, Any] | None:
    for index, record in enumerate(payload.get("records", []), start=1):
        if isinstance(record, dict) and record.get("ok") is False:
            return {
                "index": index,
                "command": record.get("command"),
                "exitCode": record.get("exitCode"),
                "message": failure_message(record),
            }
    for record in payload.get("validations", []):
        if isinstance(record, dict) and record.get("errors"):
            return {
                "index": record.get("index"),
                "command": record.get("command"),
                "exitCode": None,
                "message": str(record.get("errors", ["validation failed"])[0]),
            }
    return None


def load_next_task_run(
    evidence_dir: Path,
    fallback_queue_source: str = "generated",
    fallback_queue_source_origin: str = "default-generated",
) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "next-version-task-run.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_TASK_RUN_SCHEMA:
        raise ValueError(f"{path}: unsupported next-task-run schemaVersion: {payload.get('schemaVersion')!r}")
    next_task = payload.get("nextTask") or {}
    selected = next_task.get("selected") or {}
    queue_source, queue_source_origin = resolved_queue_source(
        payload,
        fallback_queue_source,
        fallback_queue_source_origin,
    )
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "queueSource": queue_source,
        "queueSourceOrigin": queue_source_origin,
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "clusterWrites": payload.get("clusterWrites"),
        "ranAt": payload.get("ranAt"),
        "summary": payload.get("summary", {}),
        "failure": payload.get("failure") if isinstance(payload.get("failure"), dict) else next_task_run_failure(payload),
        "selected": {
            "id": selected.get("id"),
            "version": selected.get("version"),
            "item": selected.get("item"),
            "kind": selected.get("kind"),
            "captureStatus": selected.get("captureStatus"),
            "environmentStatus": selected.get("environmentStatus"),
            "environmentReason": selected.get("environmentReason"),
            "missingTools": selected.get("missingTools", []),
            "nextStep": selected.get("nextStep"),
        },
    }


def next_unblock_selected_summary(selected: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": selected.get("id"),
        "kind": selected.get("kind"),
        "target": selected.get("tool") or selected.get("environmentStatus"),
        "tool": selected.get("tool"),
        "environmentStatus": selected.get("environmentStatus"),
        "environmentReason": selected.get("environmentReason"),
        "items": selected.get("items", 0),
        "affectedVersions": selected.get("affectedVersions", []),
        "nextStep": selected.get("nextStep"),
        "commands": selected.get("commands", {}),
    }


def load_next_unblock_action(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "next-unblock-action.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_UNBLOCK_ACTION_SCHEMA:
        raise ValueError(f"{path}: unsupported next-unblock-action schemaVersion: {payload.get('schemaVersion')!r}")
    selected = payload.get("selected") if isinstance(payload.get("selected"), dict) else {}
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "queueSource": payload.get("sourceWorklistQueueSource") or "generated",
        "status": payload.get("status"),
        "planStatus": payload.get("planStatus"),
        "clusterWrites": payload.get("clusterWrites"),
        "selectionPolicy": payload.get("selectionPolicy"),
        "summary": payload.get("summary", {}),
        "selected": next_unblock_selected_summary(selected),
    }


def next_unblock_run_failure(payload: dict[str, Any]) -> dict[str, Any] | None:
    failure = payload.get("failure")
    if isinstance(failure, dict):
        return failure
    for record in payload.get("records", []):
        if isinstance(record, dict) and record.get("ok") is False:
            return {
                "command": record.get("command"),
                "exitCode": record.get("exitCode"),
                "message": failure_message(record),
            }
    for record in payload.get("validations", []):
        if isinstance(record, dict) and record.get("errors"):
            return {
                "command": record.get("command"),
                "exitCode": None,
                "message": str(record.get("errors", ["validation failed"])[0]),
            }
    return None


def load_next_unblock_action_run(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "next-unblock-action-run.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_UNBLOCK_ACTION_RUN_SCHEMA:
        raise ValueError(
            f"{path}: unsupported next-unblock-action-run schemaVersion: {payload.get('schemaVersion')!r}"
        )
    action = payload.get("nextUnblockAction") if isinstance(payload.get("nextUnblockAction"), dict) else {}
    selected = action.get("selected") if isinstance(action.get("selected"), dict) else {}
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "queueSource": action.get("queueSource") or "generated",
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "clusterWrites": payload.get("clusterWrites"),
        "ranAt": payload.get("ranAt"),
        "summary": payload.get("summary", {}),
        "failure": next_unblock_run_failure(payload),
        "selected": {
            "id": selected.get("id"),
            "kind": selected.get("kind"),
            "target": selected.get("target"),
            "tool": selected.get("tool"),
            "environmentStatus": selected.get("environmentStatus"),
            "environmentReason": selected.get("environmentReason"),
            "items": selected.get("items", 0),
            "affectedVersions": selected.get("affectedVersions", []),
            "nextStep": selected.get("nextStep"),
        },
    }


def load_next_task_evidence_build(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "next-task-evidence-build.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_TASK_BUILD_SCHEMA:
        raise ValueError(f"{path}: unsupported next-task-evidence-build schemaVersion: {payload.get('schemaVersion')!r}")
    next_task = payload.get("nextTask") or {}
    selected = next_task.get("selected") or {}
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "builtAt": payload.get("builtAt"),
        "summary": payload.get("summary", {}),
        "selected": {
            "id": selected.get("id"),
            "version": selected.get("version"),
            "item": selected.get("item"),
            "kind": selected.get("kind"),
            "captureStatus": selected.get("captureStatus"),
            "environmentStatus": selected.get("environmentStatus"),
            "environmentReason": selected.get("environmentReason"),
            "missingTools": selected.get("missingTools", []),
            "nextStep": selected.get("nextStep"),
        },
        "records": [
            {
                "status": record.get("status"),
                "kind": record.get("kind"),
                "source": record.get("source"),
                "output": record.get("output"),
            }
            for record in payload.get("records", [])
            if isinstance(record, dict)
        ],
        "errors": payload.get("errors", []),
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
        "reason": payload.get("reason"),
        "kubectl": payload.get("kubectl"),
        "summary": payload.get("summary", {}),
    }


def load_environment_blockers(
    evidence_dir: Path,
    version_filters: list[str] | None = None,
) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "environment-blockers.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != ENVIRONMENT_BLOCKERS_SCHEMA:
        raise ValueError(f"{path}: unsupported environment-blockers schemaVersion: {payload.get('schemaVersion')!r}")
    requested = set(version_filters or [])
    items = [
        item
        for item in payload.get("items", [])
        if isinstance(item, dict) and (not requested or item.get("version") in requested)
    ]
    selected = payload.get("selected") if isinstance(payload.get("selected"), dict) else {}
    summary = dict(payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {})
    if requested:
        summary["blockedByEnvironment"] = len(items)
        summary["selectedBlocked"] = (
            selected.get("version") in requested
            and selected.get("captureStatus") == "blocked-by-environment"
        )
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "clusterWrites": payload.get("clusterWrites"),
        "summary": summary,
        "selected": selected,
        "items": items,
    }


def load_version_iteration_advance(
    evidence_dir: Path,
    fallback_queue_source: str = "generated",
    fallback_queue_source_origin: str = "default-generated",
) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "version-iteration-advance.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != ADVANCE_SCHEMA:
        raise ValueError(f"{path}: unsupported version-iteration-advance schemaVersion: {payload.get('schemaVersion')!r}")
    runner = payload.get("runner") or {}
    next_task = payload.get("nextTask") or {}
    queue_source, queue_source_origin = resolved_queue_source(
        payload,
        fallback_queue_source,
        fallback_queue_source_origin,
    )
    return {
        "schemaVersion": payload.get("schemaVersion"),
        "path": str(path),
        "queueSource": queue_source,
        "queueSourceOrigin": queue_source_origin,
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "clusterWrites": payload.get("clusterWrites"),
        "runId": payload.get("runId"),
        "createdAt": payload.get("createdAt"),
        "runnerStatus": runner.get("status"),
        "nextTask": {
            "selected": next_task.get("selected"),
            "captureStatus": next_task.get("captureStatus"),
            "skippedCompleteEvidence": next_task.get("skippedCompleteEvidence"),
        },
        "history": payload.get("history", {}),
        "latestBlockerStreak": payload.get("latestBlockerStreak"),
    }


def load_live_validation_queue(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "live-validation-queue.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != LIVE_QUEUE_SCHEMA:
        raise ValueError(f"{path}: unsupported live-validation-queue schemaVersion: {payload.get('schemaVersion')!r}")
    return payload


def command_string(args: list[str]) -> str:
    return " ".join(shlex.quote(arg) for arg in args)


def add_repeated_args(args: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        args.extend([flag, str(value)])


def blocker_worklist_command(
    capture_status: str,
    filter_flag: str,
    filter_value: str,
    evidence_dir: Path,
    version_filters: list[str] | None = None,
) -> str:
    args = [
        "python3",
        "-B",
        "scripts/generate_version_worklist.py",
        "--format",
        "markdown",
        "--open-only",
        "--evidence-dir",
        evidence_dir.as_posix(),
    ]
    add_repeated_args(args, "--version", list(version_filters or []))
    args.extend(["--capture-status", capture_status, filter_flag, filter_value])
    return command_string(args)


def selected_worklist_commands(selected: dict[str, Any], evidence_dir: Path) -> list[str]:
    args = [
        "python3",
        "-B",
        "scripts/generate_version_worklist.py",
        "--format",
        "markdown",
        "--open-only",
        "--evidence-dir",
        evidence_dir.as_posix(),
    ]
    if selected.get("version"):
        args.extend(["--version", str(selected["version"])])
    capture_status = selected.get("captureStatus")
    if capture_status:
        args.extend(["--capture-status", str(capture_status)])
    if capture_status == "missing-tools" and selected.get("missingTools"):
        return [
            command_string([*args, "--missing-tool", str(tool)])
            for tool in selected.get("missingTools", [])
        ]
    if capture_status == "blocked-by-environment" and selected.get("environmentStatus"):
        args.extend(["--environment-status", str(selected["environmentStatus"])])
    if capture_status == "blocked-by-environment" and selected.get("environmentReason"):
        args.extend(["--environment-reason", str(selected["environmentReason"])])
    return [command_string(args)]


def sorted_counts(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def live_queue_blockers(
    live_queue: dict[str, Any] | None,
    evidence_dir: Path,
    version_filters: list[str] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(live_queue, dict):
        return None
    requested = set(version_filters or [])
    items = [
        item
        for item in live_queue.get("items", [])
        if isinstance(item, dict) and (not requested or item.get("version") in requested)
    ]
    missing_tools = Counter(
        str(tool)
        for item in items
        if item.get("status") == "missing-tools"
        for tool in item.get("missingTools", [])
    )
    environment_statuses = Counter(
        str(item.get("environmentStatus") or "unknown")
        for item in items
        if item.get("status") == "blocked-by-environment"
    )
    environment_reasons = Counter(
        str(item.get("environmentReason") or "unknown")
        for item in items
        if item.get("status") == "blocked-by-environment"
    )
    environment_next_steps = Counter(
        str(item.get("nextStep"))
        for item in items
        if item.get("status") == "blocked-by-environment" and item.get("nextStep")
    )
    return {
        "missingTools": [
            {
                "tool": tool,
                "items": count,
                "worklistCommand": blocker_worklist_command(
                    "missing-tools",
                    "--missing-tool",
                    tool,
                    evidence_dir,
                    version_filters=version_filters,
                ),
            }
            for tool, count in sorted_counts(missing_tools)
        ],
        "environment": [
            {
                "status": status,
                "items": count,
                "worklistCommand": blocker_worklist_command(
                    "blocked-by-environment",
                    "--environment-status",
                    status,
                    evidence_dir,
                    version_filters=version_filters,
                ),
            }
            for status, count in sorted_counts(environment_statuses)
        ],
        "environmentReasons": [
            {
                "reason": reason,
                "items": count,
                "worklistCommand": blocker_worklist_command(
                    "blocked-by-environment",
                    "--environment-reason",
                    reason,
                    evidence_dir,
                    version_filters=version_filters,
                ),
            }
            for reason, count in sorted_counts(environment_reasons)
        ],
        "environmentNextSteps": [
            {"nextStep": next_step, "items": count}
            for next_step, count in sorted_counts(environment_next_steps)
        ],
    }


def unique_commands(
    gates: list[dict[str, Any]],
    skip_gate_ids: set[str] | None = None,
    include_closure: bool = True,
) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    skip_gate_ids = skip_gate_ids or set()
    for gate in gates:
        if str(gate.get("id")) in skip_gate_ids:
            continue
        for command in gate.get("recommendedCommands", []):
            if command not in seen:
                commands.append(command)
                seen.add(command)
    if include_closure and "python3 -B scripts/build_release_evidence_directory.py <evidence-dir>" not in seen:
        commands.append("python3 -B scripts/build_release_evidence_directory.py <evidence-dir>")
    return commands


def selected_resolved_commands(next_task: dict[str, Any] | None) -> list[str]:
    selected = next_task.get("selected", {}) if isinstance(next_task, dict) else {}
    return [
        command
        for command in selected.get("resolvedCommands", [])
        if isinstance(command, str)
    ]


def queue_items_by_id(live_queue: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(live_queue, dict):
        return {}
    return {
        str(item.get("id")): item
        for item in live_queue.get("items", [])
        if isinstance(item, dict) and item.get("id")
    }


def gate_scope(gate: dict[str, Any]) -> str | None:
    return gate.get("version") or gate.get("section")


def next_task_queue_consistency(next_task: dict[str, Any] | None, live_queue: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(next_task, dict):
        return None
    selected = next_task.get("selected") or {}
    selected_id = selected.get("id")
    if not isinstance(live_queue, dict):
        return {
            "status": "not-checked",
            "reason": "live validation queue not found",
            "selected": selected_id,
        }
    if not selected_id:
        return {
            "status": "not-checked",
            "reason": "selected next-task id missing",
            "selected": None,
        }
    item = queue_items_by_id(live_queue).get(str(selected_id))
    if not item:
        return {
            "status": "missing",
            "reason": "selected next-task id not found in live validation queue",
            "selected": selected_id,
        }
    mismatches: list[str] = []
    comparisons = (
        ("kind", selected.get("kind"), item.get("kind")),
        ("version", selected.get("version"), item.get("version")),
        ("captureStatus", selected.get("captureStatus"), item.get("status")),
        ("commands", selected.get("commands", []), item.get("commands", [])),
        ("resolvedCommands", selected.get("resolvedCommands", []), item.get("resolvedCommands", [])),
    )
    for field, selected_value, queue_value in comparisons:
        if selected_value != queue_value:
            mismatches.append(field)
    return {
        "status": "matched" if not mismatches else "mismatched",
        "selected": selected_id,
        "queueItemStatus": item.get("status"),
        "selectedStatus": selected.get("captureStatus"),
        "mismatches": mismatches,
    }


def record_next_task_consistency(
    next_task: dict[str, Any] | None,
    record_selected: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(next_task, dict) or not isinstance(record_selected, dict):
        return None
    selected = next_task.get("selected") or {}
    selected_id = selected.get("id")
    record_id = record_selected.get("id") or record_selected.get("selected")
    if not selected_id or not record_id:
        return {
            "status": "not-checked",
            "reason": "selected next-task id missing",
            "selected": selected_id,
            "recordSelected": record_id,
        }
    comparisons = (
        ("id", selected_id, record_id),
        ("version", selected.get("version"), record_selected.get("version")),
        ("kind", selected.get("kind"), record_selected.get("kind")),
        ("captureStatus", selected.get("captureStatus"), record_selected.get("captureStatus")),
    )
    mismatches = [
        field
        for field, selected_value, record_value in comparisons
        if record_value is not None and selected_value != record_value
    ]
    return {
        "status": "matched" if not mismatches else "mismatched",
        "selected": selected_id,
        "recordSelected": record_id,
        "mismatches": mismatches,
    }


def queue_resolved_commands(
    gates: list[dict[str, Any]],
    live_queue: dict[str, Any] | None,
    skip_gate_ids: set[str],
    version_filters: list[str] | None = None,
) -> tuple[list[str], set[str]]:
    commands: list[str] = []
    command_gate_ids: set[str] = set()
    items = queue_items_by_id(live_queue)
    requested = set(version_filters or [])
    for gate in gates:
        gate_id = str(gate.get("id"))
        if gate_id in skip_gate_ids:
            continue
        item = items.get(gate_id)
        if not item:
            continue
        if requested and item.get("version") not in requested:
            continue
        if item.get("status") != "tool-ready":
            continue
        item_commands = item.get("resolvedCommands") or item.get("commands") or []
        for command in item_commands:
            if isinstance(command, str) and command not in commands:
                commands.append(command)
        if item_commands:
            command_gate_ids.add(gate_id)
    return commands, command_gate_ids


def queue_closure_commands(live_queue: dict[str, Any] | None) -> list[str]:
    if not isinstance(live_queue, dict):
        return []
    return [
        command
        for command in live_queue.get("resolvedClosureCommands", [])
        if isinstance(command, str)
    ]


def next_commands(
    gates: list[dict[str, Any]],
    evidence_dir: Path,
    next_task: dict[str, Any] | None,
    live_queue: dict[str, Any] | None,
    environment_probe: dict[str, Any] | None,
    environment_blockers: dict[str, Any] | None,
    next_task_run: dict[str, Any] | None,
    next_unblock_action: dict[str, Any] | None,
    next_unblock_action_run: dict[str, Any] | None,
    version_filters: list[str] | None = None,
) -> list[str]:
    commands: list[str] = []
    requested = set(version_filters or [])
    scoped_gates = [gate for gate in gates if not requested or gate_scope(gate) in requested]
    resolved = selected_resolved_commands(next_task)
    selected = next_task.get("selected", {}) if isinstance(next_task, dict) else {}
    selected_id = str(selected.get("id")) if selected.get("id") else None
    selected_version = selected.get("version")
    selected_in_scope = not requested or selected_version in requested
    selected_status = selected.get("captureStatus")
    blocker_summary = environment_blockers.get("summary", {}) if isinstance(environment_blockers, dict) else {}
    selected_blocked = blocker_summary.get("selectedBlocked") is True
    scoped_environment_blocked = bool(requested) and blocker_summary.get("blockedByEnvironment", 0) > 0
    selected_ready = selected_status == "tool-ready" and not selected_blocked
    skip_gate_ids = {selected_id} if selected_id and selected_in_scope else set()
    queue_commands, queue_gate_ids = queue_resolved_commands(
        scoped_gates,
        live_queue,
        skip_gate_ids,
        version_filters=version_filters,
    )
    closure_commands = queue_closure_commands(live_queue)
    fallback_commands = unique_commands(
        scoped_gates,
        skip_gate_ids | queue_gate_ids,
        include_closure=not closure_commands and live_queue is None,
    )
    selected_commands = resolved if selected_ready and selected_in_scope else []
    queue_or_fallback_commands = queue_commands if live_queue is not None else fallback_commands
    include_closure = bool(queue_or_fallback_commands or selected_commands)
    for command in [
        *selected_commands,
        *queue_or_fallback_commands,
        *(closure_commands if include_closure else []),
    ]:
        if command not in commands:
            commands.append(command)
    unblock_command = next_unblock_retry_command(
        evidence_dir,
        next_unblock_action,
        next_unblock_action_run,
        version_filters=version_filters,
    )
    if unblock_command and unblock_command not in commands:
        commands.append(unblock_command)
    probe_status = environment_probe.get("clusterAccess") if isinstance(environment_probe, dict) else None
    runner_status = next_task_run.get("status") if isinstance(next_task_run, dict) else None
    if selected_blocked or scoped_environment_blocked or (runner_status == "failed" and probe_status in {None, "not-run"}):
        probe_args = [
            "python3",
            "-B",
            "scripts/prepare_live_evidence_directory.py",
            evidence_dir.as_posix(),
        ]
        add_repeated_args(probe_args, "--version", list(version_filters or []))
        probe_args.append("--probe-environment")
        probe_command = command_string(probe_args)
        if probe_command not in commands:
            commands.insert(0, probe_command)
    return commands


def next_unblock_retry_command(
    evidence_dir: Path,
    next_unblock_action: dict[str, Any] | None,
    next_unblock_action_run: dict[str, Any] | None,
    version_filters: list[str] | None = None,
) -> str | None:
    if not isinstance(next_unblock_action, dict):
        return None
    selected = next_unblock_action.get("selected")
    if not isinstance(selected, dict) or not selected.get("id"):
        return None
    requested = set(version_filters or [])
    affected_versions = {
        str(version)
        for version in selected.get("affectedVersions", [])
        if isinstance(version, str)
    }
    if requested and affected_versions and not requested.intersection(affected_versions):
        return None
    run_status = next_unblock_action_run.get("status") if isinstance(next_unblock_action_run, dict) else None
    if run_status in {"passed", "clear"}:
        return None
    return command_string(
        [
            "python3",
            "-B",
            "scripts/run_next_unblock_action.py",
            evidence_dir.as_posix(),
            "--run",
            "--record",
        ]
    )


def inspect_directory(
    evidence_dir: Path,
    output_dir: Path,
    version_filters: list[str] | None = None,
) -> dict[str, Any]:
    version_filters = list(version_filters or [])
    if not evidence_dir.is_dir():
        raise ValueError(f"{evidence_dir}: evidence directory not found")
    live_reports, supplemental_paths, errors = scan_directory(evidence_dir, output_dir, require_live_reports=False)
    if errors:
        raise ValueError("; ".join(errors))

    manifest = build_manifest(live_reports)
    evaluation = evaluate(manifest, supplemental_paths)
    coverage_errors = check_coverage(manifest)
    requested = set(version_filters)
    evaluated_gates = [gate for gate in evaluation.get("gates", []) if isinstance(gate, dict)]
    scoped_gates = [
        gate
        for gate in evaluated_gates
        if not requested or gate_scope(gate) in requested
    ]
    scoped_coverage_errors = [] if requested else coverage_errors
    supplemental = [load_supplemental(path) for path in supplemental_paths]
    live_queue = load_live_validation_queue(evidence_dir)
    blockers = live_queue_blockers(live_queue, evidence_dir, version_filters=version_filters)
    fallback_queue_source, fallback_queue_source_origin = default_queue_source(live_queue)
    next_task = load_next_task(evidence_dir, fallback_queue_source, fallback_queue_source_origin)
    if next_task is not None:
        next_task["queueConsistency"] = next_task_queue_consistency(next_task, live_queue)
        next_task["worklistCommands"] = selected_worklist_commands(next_task.get("selected", {}), evidence_dir)
    next_task_run = load_next_task_run(evidence_dir, fallback_queue_source, fallback_queue_source_origin)
    next_unblock_action = load_next_unblock_action(evidence_dir)
    next_unblock_action_run = load_next_unblock_action_run(evidence_dir)
    next_task_evidence_build = load_next_task_evidence_build(evidence_dir)
    environment_probe = load_environment_probe(evidence_dir)
    environment_blockers = load_environment_blockers(evidence_dir, version_filters=version_filters)
    version_iteration_advance = load_version_iteration_advance(
        evidence_dir,
        fallback_queue_source,
        fallback_queue_source_origin,
    )
    if next_task_run is not None:
        fill_selected_metadata(next_task_run, next_task)
        next_task_run["nextTaskConsistency"] = record_next_task_consistency(
            next_task,
            next_task_run.get("selected"),
        )
    if next_task_evidence_build is not None:
        fill_selected_metadata(next_task_evidence_build, next_task)
        next_task_evidence_build["nextTaskConsistency"] = record_next_task_consistency(
            next_task,
            next_task_evidence_build.get("selected"),
        )
    if version_iteration_advance is not None:
        version_iteration_advance["nextTaskConsistency"] = record_next_task_consistency(
            next_task,
            version_iteration_advance.get("nextTask"),
        )
    uncovered = [gate for gate in scoped_gates if gate.get("covered") is not True]
    covered_count = sum(1 for gate in scoped_gates if gate.get("covered") is True)
    summary = {
        "total": len(scoped_gates),
        "covered": covered_count,
        "uncovered": len(scoped_gates) - covered_count,
    }
    complete = summary["uncovered"] == 0 and not scoped_coverage_errors
    return {
        "schemaVersion": SCHEMA_VERSION,
        "evidenceDir": str(evidence_dir),
        "outputDir": str(output_dir),
        "filters": {
            "versions": version_filters,
        },
        "summary": {
            "status": "complete" if complete else "partial",
            "liveReports": len(live_reports),
            "supplementalEvidence": len(supplemental_paths),
            "coveredGates": summary.get("covered", 0),
            "uncoveredGates": summary.get("uncovered", 0),
            "totalGates": summary.get("total", 0),
            "coverageErrors": len(scoped_coverage_errors),
        },
        "nextTask": next_task,
        "nextTaskRun": next_task_run,
        "nextUnblockAction": next_unblock_action,
        "nextUnblockActionRun": next_unblock_action_run,
        "nextTaskEvidenceBuild": next_task_evidence_build,
        "environmentProbe": environment_probe,
        "environmentBlockers": environment_blockers,
        "versionIterationAdvance": version_iteration_advance,
        "blockers": blockers,
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
            "coverage": scoped_coverage_errors,
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
        "nextCommands": next_commands(
            uncovered,
            evidence_dir,
            next_task,
            live_queue,
            environment_probe,
            environment_blockers,
            next_task_run,
            next_unblock_action,
            next_unblock_action_run,
            version_filters=version_filters,
        ),
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
    filters = status.get("filters", {})
    if isinstance(filters, dict):
        for version in filters.get("versions", []) or []:
            lines.append(f"filter-version: {version}")
    for command in status["nextCommands"]:
        lines.append(f"next: {command}")
    next_task = status.get("nextTask")
    selected = next_task.get("selected", {}) if isinstance(next_task, dict) else {}
    if selected:
        lines.append(f"next-task: {selected.get('id')}")
        if next_task.get("queueSource"):
            lines.append(f"next-task-queue-source: {next_task.get('queueSource')}")
        if next_task.get("queueSourceOrigin"):
            lines.append(f"next-task-queue-source-origin: {next_task.get('queueSourceOrigin')}")
        consistency = next_task.get("queueConsistency") or {}
        if consistency.get("status"):
            lines.append(f"next-task-queue-consistency: {consistency.get('status')}")
            if consistency.get("mismatches"):
                lines.append(f"next-task-queue-mismatches: {', '.join(consistency.get('mismatches', []))}")
        lines.append(f"next-task-status: {selected.get('captureStatus')}")
        file_summary = next_task.get("summary", {}) if isinstance(next_task, dict) else {}
        if file_summary:
            lines.append(
                f"next-task-files: {file_summary.get('existingFiles', 0)}/{file_summary.get('files', 0)}"
            )
        for item in selected.get("files", []):
            file_status = "present" if item.get("exists") else "missing"
            lines.append(f"next-task-file: {file_status} {item.get('role')} {item.get('path')}")
        for command in selected.get("resolvedCommands", []):
            lines.append(f"next-task-command: {command}")
        for command in next_task.get("worklistCommands", []):
            lines.append(f"next-task-worklist: {command}")
    next_task_run = status.get("nextTaskRun")
    if isinstance(next_task_run, dict):
        lines.append(f"next-task-run: {next_task_run.get('status')}")
        if next_task_run.get("queueSource"):
            lines.append(f"next-task-run-queue-source: {next_task_run.get('queueSource')}")
        if next_task_run.get("queueSourceOrigin"):
            lines.append(f"next-task-run-queue-source-origin: {next_task_run.get('queueSourceOrigin')}")
        consistency = next_task_run.get("nextTaskConsistency") or {}
        if consistency.get("status"):
            lines.append(f"next-task-run-consistency: {consistency.get('status')}")
            if consistency.get("mismatches"):
                lines.append(f"next-task-run-mismatches: {', '.join(consistency.get('mismatches', []))}")
        lines.append(f"next-task-run-mode: {next_task_run.get('mode')}")
        run_summary = next_task_run.get("summary", {})
        if run_summary:
            lines.append(f"next-task-run-ran: {run_summary.get('ran', 0)}")
        failure = next_task_run.get("failure")
        if isinstance(failure, dict) and failure.get("message"):
            lines.append(f"next-task-run-error: {failure.get('message')}")
    next_unblock_action = status.get("nextUnblockAction")
    if isinstance(next_unblock_action, dict):
        selected_unblock = next_unblock_action.get("selected") or {}
        if selected_unblock.get("id"):
            lines.append(f"next-unblock-action: {selected_unblock.get('id')}")
            lines.append(f"next-unblock-action-target: {selected_unblock.get('target')}")
            lines.append(f"next-unblock-action-kind: {selected_unblock.get('kind')}")
            if next_unblock_action.get("queueSource"):
                lines.append(f"next-unblock-action-queue-source: {next_unblock_action.get('queueSource')}")
            if selected_unblock.get("items") is not None:
                lines.append(f"next-unblock-action-items: {selected_unblock.get('items')}")
            if selected_unblock.get("nextStep"):
                lines.append(f"next-unblock-action-next-step: {selected_unblock.get('nextStep')}")
            commands = selected_unblock.get("commands") if isinstance(selected_unblock.get("commands"), dict) else {}
            for command in commands.get("verify") or []:
                lines.append(f"next-unblock-action-verify: {command}")
    next_unblock_action_run = status.get("nextUnblockActionRun")
    if isinstance(next_unblock_action_run, dict):
        lines.append(f"next-unblock-action-run: {next_unblock_action_run.get('status')}")
        lines.append(f"next-unblock-action-run-mode: {next_unblock_action_run.get('mode')}")
        run_summary = next_unblock_action_run.get("summary", {})
        if run_summary:
            lines.append(f"next-unblock-action-run-ran: {run_summary.get('ran', 0)}")
            lines.append(f"next-unblock-action-run-failed: {run_summary.get('failed', 0)}")
        failure = next_unblock_action_run.get("failure")
        if isinstance(failure, dict) and failure.get("message"):
            lines.append(f"next-unblock-action-run-error: {failure.get('message')}")
    next_task_evidence_build = status.get("nextTaskEvidenceBuild")
    if isinstance(next_task_evidence_build, dict):
        build_summary = next_task_evidence_build.get("summary", {})
        lines.append(f"next-task-evidence-build: {build_summary.get('status')}")
        consistency = next_task_evidence_build.get("nextTaskConsistency") or {}
        if consistency.get("status"):
            lines.append(f"next-task-evidence-build-consistency: {consistency.get('status')}")
            if consistency.get("mismatches"):
                lines.append(f"next-task-evidence-build-mismatches: {', '.join(consistency.get('mismatches', []))}")
        if build_summary:
            lines.append(f"next-task-evidence-build-built: {build_summary.get('built', 0)}")
            lines.append(f"next-task-evidence-build-skipped: {build_summary.get('skipped', 0)}")
            lines.append(f"next-task-evidence-build-errors: {build_summary.get('errors', 0)}")
    environment_probe = status.get("environmentProbe")
    if isinstance(environment_probe, dict):
        lines.append(f"environment-probe: {environment_probe.get('clusterAccess')}")
        if environment_probe.get("reason"):
            lines.append(f"environment-probe-reason: {environment_probe.get('reason')}")
        probe_summary = environment_probe.get("summary", {})
        if probe_summary:
            lines.append(f"environment-probe-checks: {probe_summary.get('passed', 0)}/{probe_summary.get('checks', 0)}")
    environment_blockers = status.get("environmentBlockers")
    if isinstance(environment_blockers, dict):
        blocker_summary = environment_blockers.get("summary", {})
        lines.append(f"environment-blockers: {blocker_summary.get('blockedByEnvironment', 0)}")
        selected_blocker = environment_blockers.get("selected") or {}
        if selected_blocker.get("nextStep"):
            lines.append(f"environment-next: {selected_blocker.get('nextStep')}")
    blockers = status.get("blockers")
    if isinstance(blockers, dict):
        for item in blockers.get("missingTools", []):
            lines.append(f"missing-tool-blocker: {item.get('tool')} {item.get('items')}")
            if item.get("worklistCommand"):
                lines.append(f"missing-tool-worklist: {item.get('worklistCommand')}")
        for item in blockers.get("environment", []):
            lines.append(f"environment-blocker: {item.get('status')} {item.get('items')}")
            if item.get("worklistCommand"):
                lines.append(f"environment-worklist: {item.get('worklistCommand')}")
        for item in blockers.get("environmentReasons", []):
            lines.append(f"environment-reason-blocker: {item.get('reason')} {item.get('items')}")
            if item.get("worklistCommand"):
                lines.append(f"environment-reason-worklist: {item.get('worklistCommand')}")
        for item in blockers.get("environmentNextSteps", []):
            lines.append(f"blocker-next-step: {item.get('nextStep')} {item.get('items')}")
    advance = status.get("versionIterationAdvance")
    if isinstance(advance, dict):
        lines.append(f"version-iteration-advance: {advance.get('status')}")
        if advance.get("queueSource"):
            lines.append(f"version-iteration-advance-queue-source: {advance.get('queueSource')}")
        if advance.get("queueSourceOrigin"):
            lines.append(f"version-iteration-advance-queue-source-origin: {advance.get('queueSourceOrigin')}")
        consistency = advance.get("nextTaskConsistency") or {}
        if consistency.get("status"):
            lines.append(f"version-iteration-advance-consistency: {consistency.get('status')}")
            if consistency.get("mismatches"):
                lines.append(f"version-iteration-advance-mismatches: {', '.join(consistency.get('mismatches', []))}")
        blocker_streak = advance.get("latestBlockerStreak")
        if isinstance(blocker_streak, dict):
            signature = blocker_streak.get("signature", {})
            if not isinstance(signature, dict):
                signature = {}
            lines.append(f"version-iteration-advance-blocker-streak: {blocker_streak.get('streak')}")
            lines.append(f"version-iteration-advance-blocker-status: {blocker_streak.get('status')}")
            lines.append(f"version-iteration-advance-blocker-id: {signature.get('id')}")
            if signature.get("environmentReason"):
                lines.append(f"version-iteration-advance-blocker-reason: {signature.get('environmentReason')}")
        if advance.get("runId"):
            lines.append(f"version-iteration-advance-run-id: {advance.get('runId')}")
    return "\n".join(lines) + "\n"


def render_markdown(status: dict[str, Any]) -> str:
    summary = status["summary"]
    lines = [
        "# KubeActuary Release Evidence Status",
        "",
        f"Schema: `{status['schemaVersion']}`",
        f"Evidence directory: `{status['evidenceDir']}`",
        f"Status: `{summary['status']}`",
        "",
        "## Summary",
        "",
        f"- live reports: {summary['liveReports']}",
        f"- supplemental evidence: {summary['supplementalEvidence']}",
        f"- covered gates: {summary['coveredGates']}/{summary['totalGates']}",
        f"- coverage errors: {summary['coverageErrors']}",
        "",
    ]
    filters = status.get("filters", {})
    if isinstance(filters, dict) and filters.get("versions"):
        lines.extend(["## Filters", "", f"- versions: `{', '.join(str(version) for version in filters['versions'])}`", ""])
    lines.extend(["## Next Task", ""])
    next_task = status.get("nextTask")
    selected = next_task.get("selected", {}) if isinstance(next_task, dict) else {}
    if selected:
        lines.append(f"- `{selected.get('id')}` {selected.get('item')} ({selected.get('captureStatus')})")
        if next_task.get("queueSource"):
            lines.append(f"- queue source: `{next_task.get('queueSource')}`")
        if next_task.get("queueSourceOrigin"):
            lines.append(f"- queue source origin: `{next_task.get('queueSourceOrigin')}`")
        consistency = next_task.get("queueConsistency") or {}
        if consistency.get("status"):
            lines.append(f"- queue consistency: `{consistency.get('status')}`")
            if consistency.get("mismatches"):
                lines.append(f"- queue mismatches: `{', '.join(consistency.get('mismatches', []))}`")
        file_summary = next_task.get("summary", {}) if isinstance(next_task, dict) else {}
        if file_summary:
            lines.append(f"- files: {file_summary.get('existingFiles', 0)}/{file_summary.get('files', 0)}")
        for item in selected.get("files", []):
            file_status = "present" if item.get("exists") else "missing"
            lines.append(f"- file: `{file_status}` `{item.get('role')}` `{item.get('path')}`")
        for command in selected.get("resolvedCommands", []):
            lines.append(f"- command: `{command}`")
        for command in next_task.get("worklistCommands", []):
            lines.append(f"- worklist: `{command}`")
    else:
        lines.append("- none")
    next_task_run = status.get("nextTaskRun")
    if isinstance(next_task_run, dict):
        lines.extend(["", "## Runner", "", f"- status: `{next_task_run.get('status')}`"])
        if next_task_run.get("queueSource"):
            lines.append(f"- queue source: `{next_task_run.get('queueSource')}`")
        if next_task_run.get("queueSourceOrigin"):
            lines.append(f"- queue source origin: `{next_task_run.get('queueSourceOrigin')}`")
        consistency = next_task_run.get("nextTaskConsistency") or {}
        if consistency.get("status"):
            lines.append(f"- next-task consistency: `{consistency.get('status')}`")
            if consistency.get("mismatches"):
                lines.append(f"- next-task mismatches: `{', '.join(consistency.get('mismatches', []))}`")
        run_summary = next_task_run.get("summary", {})
        if run_summary:
            lines.append(f"- ran: {run_summary.get('ran', 0)}")
        failure = next_task_run.get("failure")
        if isinstance(failure, dict) and failure.get("message"):
            lines.append(f"- error: `{failure.get('message')}`")
    next_unblock_action = status.get("nextUnblockAction")
    next_unblock_action_run = status.get("nextUnblockActionRun")
    if isinstance(next_unblock_action, dict) or isinstance(next_unblock_action_run, dict):
        lines.extend(["", "## Next Unblock", ""])
        if isinstance(next_unblock_action, dict):
            selected_unblock = next_unblock_action.get("selected") or {}
            if selected_unblock.get("id"):
                lines.append(
                    f"- action: `{selected_unblock.get('id')}` "
                    f"target=`{selected_unblock.get('target')}`"
                )
                lines.append(f"- kind: `{selected_unblock.get('kind')}`")
                lines.append(f"- items: {selected_unblock.get('items', 0)}")
                if next_unblock_action.get("queueSource"):
                    lines.append(f"- queue source: `{next_unblock_action.get('queueSource')}`")
                if selected_unblock.get("nextStep"):
                    lines.append(f"- next step: {selected_unblock.get('nextStep')}")
                commands = selected_unblock.get("commands") if isinstance(selected_unblock.get("commands"), dict) else {}
                for command in commands.get("verify") or []:
                    lines.append(f"- verify: `{command}`")
        if isinstance(next_unblock_action_run, dict):
            lines.append(f"- run: `{next_unblock_action_run.get('status')}` ({next_unblock_action_run.get('mode')})")
            run_summary = next_unblock_action_run.get("summary", {})
            if run_summary:
                lines.append(f"- run commands: {run_summary.get('ran', 0)}")
                lines.append(f"- run failed: {run_summary.get('failed', 0)}")
            failure = next_unblock_action_run.get("failure")
            if isinstance(failure, dict) and failure.get("message"):
                lines.append(f"- run error: `{failure.get('message')}`")
    next_task_evidence_build = status.get("nextTaskEvidenceBuild")
    if isinstance(next_task_evidence_build, dict):
        build_summary = next_task_evidence_build.get("summary", {})
        lines.extend(["", "## Evidence Build", "", f"- status: `{build_summary.get('status')}`"])
        consistency = next_task_evidence_build.get("nextTaskConsistency") or {}
        if consistency.get("status"):
            lines.append(f"- next-task consistency: `{consistency.get('status')}`")
            if consistency.get("mismatches"):
                lines.append(f"- next-task mismatches: `{', '.join(consistency.get('mismatches', []))}`")
        lines.append(f"- built: {build_summary.get('built', 0)}")
        lines.append(f"- skipped: {build_summary.get('skipped', 0)}")
        lines.append(f"- errors: {build_summary.get('errors', 0)}")
        for record in next_task_evidence_build.get("records", []):
            lines.append(f"- record: `{record.get('status')}` `{record.get('kind')}` `{record.get('output')}`")
    environment_probe = status.get("environmentProbe")
    environment_blockers = status.get("environmentBlockers")
    if isinstance(environment_probe, dict) or isinstance(environment_blockers, dict):
        lines.extend(["", "## Environment", ""])
        if isinstance(environment_probe, dict):
            lines.append(f"- probe: `{environment_probe.get('clusterAccess')}`")
            if environment_probe.get("reason"):
                lines.append(f"- probe reason: `{environment_probe.get('reason')}`")
        if isinstance(environment_blockers, dict):
            blocker_summary = environment_blockers.get("summary", {})
            lines.append(f"- blockers: {blocker_summary.get('blockedByEnvironment', 0)}")
            selected_blocker = environment_blockers.get("selected") or {}
            if selected_blocker.get("nextStep"):
                lines.append(f"- next: {selected_blocker.get('nextStep')}")
    blockers = status.get("blockers")
    if isinstance(blockers, dict):
        missing_tool_blockers = blockers.get("missingTools") or []
        environment_status_blockers = blockers.get("environment") or []
        environment_reason_blockers = blockers.get("environmentReasons") or []
        environment_next_steps = blockers.get("environmentNextSteps") or []
        if missing_tool_blockers or environment_status_blockers or environment_reason_blockers:
            lines.extend(["", "## Blockers", ""])
            for item in missing_tool_blockers:
                lines.append(f"- missing-tool: `{item.get('tool')}` ({item.get('items')} items)")
                if item.get("worklistCommand"):
                    lines.append(f"  - worklist: `{item.get('worklistCommand')}`")
            for item in environment_status_blockers:
                lines.append(f"- environment: `{item.get('status')}` ({item.get('items')} items)")
                if item.get("worklistCommand"):
                    lines.append(f"  - worklist: `{item.get('worklistCommand')}`")
            for item in environment_reason_blockers:
                lines.append(f"- environment reason: `{item.get('reason')}` ({item.get('items')} items)")
                if item.get("worklistCommand"):
                    lines.append(f"  - worklist: `{item.get('worklistCommand')}`")
            for item in environment_next_steps:
                lines.append(f"- next-step: {item.get('nextStep')} ({item.get('items')} items)")
    advance = status.get("versionIterationAdvance")
    if isinstance(advance, dict):
        lines.extend(["", "## Advance", "", f"- status: `{advance.get('status')}`"])
        if advance.get("queueSource"):
            lines.append(f"- queue source: `{advance.get('queueSource')}`")
        if advance.get("queueSourceOrigin"):
            lines.append(f"- queue source origin: `{advance.get('queueSourceOrigin')}`")
        consistency = advance.get("nextTaskConsistency") or {}
        if consistency.get("status"):
            lines.append(f"- next-task consistency: `{consistency.get('status')}`")
            if consistency.get("mismatches"):
                lines.append(f"- next-task mismatches: `{', '.join(consistency.get('mismatches', []))}`")
        blocker_streak = advance.get("latestBlockerStreak")
        if isinstance(blocker_streak, dict):
            signature = blocker_streak.get("signature", {})
            if not isinstance(signature, dict):
                signature = {}
            lines.append(
                f"- latest blocker streak: `{blocker_streak.get('streak')}` "
                f"({blocker_streak.get('status')})"
            )
            lines.append(f"- latest blocker task: `{signature.get('id')}`")
            if signature.get("environmentReason"):
                lines.append(f"- latest blocker reason: `{signature.get('environmentReason')}`")
        if advance.get("runId"):
            lines.append(f"- run id: `{advance.get('runId')}`")
        history = advance.get("history", {})
        if isinstance(history, dict) and history.get("runs") is not None:
            lines.append(f"- history runs: {history.get('runs')}")
    if status.get("nextCommands"):
        lines.extend(["", "## Next Commands", ""])
        for command in status["nextCommands"]:
            lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def record_status(evidence_dir: Path, status: dict[str, Any]) -> dict[str, str]:
    metadata_dir = evidence_dir / DEFAULT_OUTPUT_DIR
    metadata_dir.mkdir(parents=True, exist_ok=True)
    json_path = metadata_dir / STATUS_REPORT_JSON
    markdown_path = metadata_dir / STATUS_REPORT_MD
    record = {"json": str(json_path), "markdown": str(markdown_path)}
    status["statusRecord"] = record
    json_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_markdown(status))
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect KubeActuary release evidence directory status.")
    parser.add_argument("evidence_dir", help="directory containing captured live and supplemental evidence JSON")
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"artifact output directory, default: <evidence-dir>/{DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--version", action="append", default=[], help="filter live queue blockers and next commands to a release version; repeatable")
    parser.add_argument("--record", action="store_true", help="write status JSON and Markdown under .kubeactuary")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    output_dir = Path(args.output_dir) if args.output_dir else evidence_dir / DEFAULT_OUTPUT_DIR
    try:
        status = inspect_directory(evidence_dir, output_dir, version_filters=args.version)
        record = record_status(evidence_dir, status) if args.record else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("release-evidence-status: failed")
        print(f"error: {exc}")
        return 1

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
        print(f"release-evidence-status: wrote {args.output}")
    if record:
        print(f"release-evidence-status: recorded {record['json']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
