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
STATUS_REPORT_JSON = "release-evidence-status.json"
STATUS_REPORT_MD = "release-evidence-status.md"
NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"
NEXT_TASK_RUN_SCHEMA = "kube-actuary.next-version-task-run.v1"
ENVIRONMENT_PROBE_SCHEMA = "kube-actuary.environment-probe.v1"
ENVIRONMENT_BLOCKERS_SCHEMA = "kube-actuary.environment-blockers.v1"
ADVANCE_SCHEMA = "kube-actuary.version-iteration-advance.v1"
LIVE_QUEUE_SCHEMA = "kube-actuary.live-validation-queue.v1"
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
            "missingTools": selected.get("missingTools", []),
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
    }


def load_live_validation_queue(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "live-validation-queue.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != LIVE_QUEUE_SCHEMA:
        raise ValueError(f"{path}: unsupported live-validation-queue schemaVersion: {payload.get('schemaVersion')!r}")
    return payload


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
) -> tuple[list[str], set[str]]:
    commands: list[str] = []
    command_gate_ids: set[str] = set()
    items = queue_items_by_id(live_queue)
    for gate in gates:
        gate_id = str(gate.get("id"))
        if gate_id in skip_gate_ids:
            continue
        item = items.get(gate_id)
        if not item:
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
) -> list[str]:
    commands: list[str] = []
    resolved = selected_resolved_commands(next_task)
    selected = next_task.get("selected", {}) if isinstance(next_task, dict) else {}
    selected_id = str(selected.get("id")) if selected.get("id") else None
    selected_status = selected.get("captureStatus")
    blocker_summary = environment_blockers.get("summary", {}) if isinstance(environment_blockers, dict) else {}
    selected_blocked = blocker_summary.get("selectedBlocked") is True
    selected_ready = selected_status == "tool-ready" and not selected_blocked
    skip_gate_ids = {selected_id} if selected_id else set()
    queue_commands, queue_gate_ids = queue_resolved_commands(gates, live_queue, skip_gate_ids)
    closure_commands = queue_closure_commands(live_queue)
    fallback_commands = unique_commands(
        gates,
        skip_gate_ids | queue_gate_ids,
        include_closure=not closure_commands and live_queue is None,
    )
    selected_commands = resolved if selected_ready else []
    queue_or_fallback_commands = queue_commands if live_queue is not None else fallback_commands
    include_closure = bool(queue_or_fallback_commands or selected_commands)
    for command in [
        *selected_commands,
        *queue_or_fallback_commands,
        *(closure_commands if include_closure else []),
    ]:
        if command not in commands:
            commands.append(command)
    probe_status = environment_probe.get("clusterAccess") if isinstance(environment_probe, dict) else None
    runner_status = next_task_run.get("status") if isinstance(next_task_run, dict) else None
    if selected_blocked or (runner_status == "failed" and probe_status in {None, "not-run"}):
        probe_command = f"python3 -B scripts/prepare_live_evidence_directory.py {evidence_dir} --probe-environment"
        if probe_command not in commands:
            commands.insert(0, probe_command)
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
    live_queue = load_live_validation_queue(evidence_dir)
    fallback_queue_source, fallback_queue_source_origin = default_queue_source(live_queue)
    next_task = load_next_task(evidence_dir, fallback_queue_source, fallback_queue_source_origin)
    if next_task is not None:
        next_task["queueConsistency"] = next_task_queue_consistency(next_task, live_queue)
    next_task_run = load_next_task_run(evidence_dir, fallback_queue_source, fallback_queue_source_origin)
    environment_probe = load_environment_probe(evidence_dir)
    environment_blockers = load_environment_blockers(evidence_dir)
    version_iteration_advance = load_version_iteration_advance(
        evidence_dir,
        fallback_queue_source,
        fallback_queue_source_origin,
    )
    if next_task_run is not None:
        next_task_run["nextTaskConsistency"] = record_next_task_consistency(
            next_task,
            next_task_run.get("selected"),
        )
    if version_iteration_advance is not None:
        version_iteration_advance["nextTaskConsistency"] = record_next_task_consistency(
            next_task,
            version_iteration_advance.get("nextTask"),
        )
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
        "versionIterationAdvance": version_iteration_advance,
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
        "nextCommands": next_commands(
            uncovered,
            evidence_dir,
            next_task,
            live_queue,
            environment_probe,
            environment_blockers,
            next_task_run,
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
        selected_blocker = environment_blockers.get("selected") or {}
        if selected_blocker.get("nextStep"):
            lines.append(f"environment-next: {selected_blocker.get('nextStep')}")
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
        "## Next Task",
        "",
    ]
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
    environment_probe = status.get("environmentProbe")
    environment_blockers = status.get("environmentBlockers")
    if isinstance(environment_probe, dict) or isinstance(environment_blockers, dict):
        lines.extend(["", "## Environment", ""])
        if isinstance(environment_probe, dict):
            lines.append(f"- probe: `{environment_probe.get('clusterAccess')}`")
        if isinstance(environment_blockers, dict):
            blocker_summary = environment_blockers.get("summary", {})
            lines.append(f"- blockers: {blocker_summary.get('blockedByEnvironment', 0)}")
            selected_blocker = environment_blockers.get("selected") or {}
            if selected_blocker.get("nextStep"):
                lines.append(f"- next: {selected_blocker.get('nextStep')}")
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
        if advance.get("runId"):
            lines.append(f"- run id: `{advance.get('runId')}`")
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
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--record", action="store_true", help="write status JSON and Markdown under .kubeactuary")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    output_dir = Path(args.output_dir) if args.output_dir else evidence_dir / DEFAULT_OUTPUT_DIR
    try:
        status = inspect_directory(evidence_dir, output_dir)
        record = record_status(evidence_dir, status) if args.record else None
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
    if record:
        print(f"release-evidence-status: recorded {record['json']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
