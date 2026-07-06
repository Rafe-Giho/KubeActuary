#!/usr/bin/env python3
"""Generate a versioned release progress report from local state."""

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

from scripts.generate_external_gate_plan import TASKBOARD, build_plan, taskboard_rows  # noqa: E402
from scripts.inspect_release_evidence_directory import DEFAULT_OUTPUT_DIR, inspect_directory  # noqa: E402
from scripts.verify_live_validation_readiness import build_report as build_readiness_report  # noqa: E402
from scripts.verify_release import COMMON_CHECKS  # noqa: E402


SCHEMA_VERSION = "kube-actuary.release-progress.v1"
LIVE_QUEUE_SCHEMA = "kube-actuary.live-validation-queue.v1"
ORDERED_STATUSES = ("DONE", "VERIFY", "DOING", "TODO", "BLOCKED")
KIND_READINESS_GATES = {
    "admission": ("admission webhook live kind smoke",),
    "controller": ("controller resource budget measurement",),
    "controller-resource-budget": ("controller resource budget measurement",),
    "crd": ("CRD live apply/explain smoke",),
    "helm": ("Helm template and install smoke",),
    "krew": ("Krew install smoke",),
    "lightweight-cluster": ("lightweight cluster smoke matrix",),
    "managed-kubernetes": ("managed Kubernetes EKS/GKE/AKS smoke",),
    "packaging": ("Helm template and install smoke", "Krew install smoke"),
}


def count_statuses(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(row["status"] for row in rows)
    return {status.lower(): counts[status] for status in ORDERED_STATUSES}


def version_key(row: dict[str, str]) -> str:
    return row.get("version") or row["section"]


def group_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(version_key(row), []).append(row)
    ordered_keys = sorted(groups, key=lambda value: (value != "Current Baseline", value))
    grouped: list[dict[str, Any]] = []
    for key in ordered_keys:
        entries = groups[key]
        grouped.append(
            {
                "version": key,
                "summary": count_statuses(entries),
                "openItems": [
                    {
                        "item": row["item"],
                        "status": row["status"],
                        "section": row["section"],
                        "evidence": row["evidence"],
                    }
                    for row in entries
                    if row["status"] != "DONE"
                ],
            }
        )
    return grouped


def filter_rows(rows: list[dict[str, str]], version_filters: list[str]) -> list[dict[str, str]]:
    if not version_filters:
        return rows
    requested = set(version_filters)
    available = {version_key(row) for row in rows}
    missing = sorted(requested - available)
    if missing:
        raise ValueError(f"unknown version: {', '.join(missing)}")
    return [row for row in rows if version_key(row) in requested]


def filter_gate_plan(plan: dict[str, Any], version_filters: list[str]) -> dict[str, Any]:
    if not version_filters:
        return plan
    requested = set(version_filters)
    gates = [
        gate
        for gate in plan.get("gates", [])
        if (gate.get("version") or gate.get("section")) in requested
    ]
    return {
        **plan,
        "summary": {
            **plan.get("summary", {}),
            "verify": len(gates),
            "doing": 0,
            "todo": 0,
            "blocked": 0,
        },
        "gates": gates,
    }


def summarize_gate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    gates = plan.get("gates", [])
    return {
        "schemaVersion": plan.get("schemaVersion"),
        "verify": plan.get("summary", {}).get("verify", 0),
        "doing": plan.get("summary", {}).get("doing", 0),
        "todo": plan.get("summary", {}).get("todo", 0),
        "gates": [
            {
                "id": gate.get("id"),
                "item": gate.get("item"),
                "kind": gate.get("kind"),
                "version": gate.get("version") or gate.get("section"),
                "firstCommand": (gate.get("recommendedCommands") or [None])[0],
            }
            for gate in gates
        ],
        "closureCommands": plan.get("closureCommands", []),
    }


def summarize_readiness(readiness: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "schemaVersion": readiness.get("schemaVersion"),
        "mode": readiness.get("mode"),
        "clusterWrites": readiness.get("clusterWrites"),
        "summary": readiness.get("summary"),
        "missingToolGates": [
            {
                "gate": gate.get("gate"),
                "missingTools": gate.get("missingTools", []),
            }
            for gate in readiness.get("gateToolReadiness", [])
            if gate.get("status") != "tool-ready"
        ],
    }
    if readiness.get("environmentProbe"):
        probe = readiness["environmentProbe"]
        summary["environmentProbe"] = {
            "clusterAccess": probe.get("clusterAccess"),
            "reason": probe.get("reason"),
            "kubectl": probe.get("kubectl"),
        }
    return summary


def environment_status_for_action(gate: dict[str, Any], readiness_by_gate: dict[str, dict[str, Any]]) -> str | None:
    readiness_gates = KIND_READINESS_GATES.get(str(gate.get("kind")), ())
    statuses = [
        readiness_by_gate.get(name, {}).get("environmentStatus")
        for name in readiness_gates
        if readiness_by_gate.get(name, {}).get("environmentStatus")
    ]
    if "cluster-unavailable" in statuses:
        return "cluster-unavailable"
    if "cluster-available" in statuses:
        return "cluster-available"
    if statuses:
        return "not-required"
    return None


def environment_reason_for_action(gate: dict[str, Any], readiness_by_gate: dict[str, dict[str, Any]]) -> str | None:
    readiness_gates = KIND_READINESS_GATES.get(str(gate.get("kind")), ())
    reasons = [
        readiness_by_gate.get(name, {}).get("environmentReason")
        for name in readiness_gates
        if readiness_by_gate.get(name, {}).get("environmentReason")
    ]
    for reason in reasons:
        if reason != "not-required":
            return str(reason)
    if reasons:
        return str(reasons[0])
    return None


def build_next_actions(
    plan: dict[str, Any],
    readiness: dict[str, Any],
    evidence_dir: Path | None = None,
    version_filters: list[str] | None = None,
) -> dict[str, Any]:
    readiness_by_gate = {
        gate.get("gate"): gate
        for gate in readiness.get("gateToolReadiness", [])
        if isinstance(gate, dict)
    }
    actions: list[dict[str, Any]] = []
    for gate in plan.get("gates", []):
        readiness_gates = KIND_READINESS_GATES.get(str(gate.get("kind")), ())
        missing_tools = sorted(
            {
                tool
                for name in readiness_gates
                for tool in readiness_by_gate.get(name, {}).get("missingTools", [])
            }
        )
        environment_status = environment_status_for_action(gate, readiness_by_gate)
        environment_reason = environment_reason_for_action(gate, readiness_by_gate)
        commands = gate.get("recommendedCommands") or []
        status = "tool-ready" if not missing_tools else "missing-tools"
        if status == "tool-ready" and environment_status == "cluster-unavailable":
            status = "blocked-by-environment"
        action = {
            "id": gate.get("id"),
            "item": gate.get("item"),
            "kind": gate.get("kind"),
            "version": gate.get("version") or gate.get("section"),
            "status": status,
            "missingTools": missing_tools,
            "nextStep": (
                "capture evidence with the listed commands"
                if status == "tool-ready"
                else "start or select a disposable cluster, then rerun the probe"
                if status == "blocked-by-environment"
                else "install missing tools or run on a host that has them"
            ),
            "firstCommand": commands[0] if status == "tool-ready" and commands else None,
        }
        if environment_status is not None:
            action["environmentStatus"] = environment_status
        if environment_reason is not None:
            action["environmentReason"] = environment_reason
        actions.append(action)
    tool_ready = sum(1 for action in actions if action["status"] == "tool-ready")
    blocked_by_environment = sum(1 for action in actions if action["status"] == "blocked-by-environment")
    blocked_by_tools = sum(1 for action in actions if action["status"] == "missing-tools")
    return {
        "source": "live-readiness-inventory",
        "summary": {
            "total": len(actions),
            "toolReady": tool_ready,
            "blockedByTools": blocked_by_tools,
            "blockedByEnvironment": blocked_by_environment,
        },
        "blockers": next_action_blockers(
            actions,
            evidence_dir=evidence_dir,
            version_filters=version_filters,
        ),
        "actions": actions,
    }


def load_live_validation_queue(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / ".kubeactuary" / "live-validation-queue.json"
    if not path.is_file():
        return None
    queue = json.loads(path.read_text())
    if queue.get("schemaVersion") != LIVE_QUEUE_SCHEMA:
        raise ValueError(f"{path}: unsupported live-validation-queue schemaVersion: {queue.get('schemaVersion')!r}")
    return queue


def next_actions_from_queue(
    queue: dict[str, Any],
    evidence_dir: Path | None = None,
    version_filters: list[str] | None = None,
) -> dict[str, Any]:
    requested = set(version_filters or [])
    actions: list[dict[str, Any]] = []
    for item in queue.get("items", []):
        if not isinstance(item, dict):
            continue
        if requested and item.get("version") not in requested:
            continue
        commands = item.get("resolvedCommands") or item.get("commands") or []
        status = item.get("status")
        actions.append(
            {
                "id": item.get("id"),
                "item": item.get("item"),
                "kind": item.get("kind"),
                "version": item.get("version"),
                "status": status,
                "missingTools": item.get("missingTools", []),
                "environmentStatus": item.get("environmentStatus"),
                "environmentReason": item.get("environmentReason"),
                "nextStep": item.get("nextStep"),
                "firstCommand": commands[0] if status == "tool-ready" and commands else None,
            }
        )
    summary = queue.get("summary", {})
    tool_ready = sum(1 for action in actions if action.get("status") == "tool-ready")
    blocked_by_tools = sum(1 for action in actions if action.get("status") == "missing-tools")
    blocked_by_environment = sum(1 for action in actions if action.get("status") == "blocked-by-environment")
    return {
        "source": "prepared-live-validation-queue",
        "summary": {
            "total": len(actions) if requested else summary.get("total", len(actions)),
            "toolReady": tool_ready if requested else summary.get("toolReady", 0),
            "blockedByTools": blocked_by_tools if requested else summary.get("blockedByTools", 0),
            "blockedByEnvironment": (
                blocked_by_environment if requested else summary.get("blockedByEnvironment", 0)
            ),
        },
        "blockers": next_action_blockers(
            actions,
            evidence_dir=evidence_dir,
            version_filters=version_filters,
        ),
        "actions": actions,
    }


def sorted_counts(counts: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"value": value, "actions": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def command_string(args: list[str]) -> str:
    return " ".join(shlex.quote(arg) for arg in args)


def blocker_worklist_command(
    capture_status: str,
    filter_flag: str,
    filter_value: str,
    evidence_dir: Path | None = None,
    version_filters: list[str] | None = None,
) -> str:
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
    for version in version_filters or []:
        args.extend(["--version", version])
    args.extend(["--capture-status", capture_status, filter_flag, filter_value])
    return command_string(args)


def next_action_blockers(
    actions: list[dict[str, Any]],
    evidence_dir: Path | None = None,
    version_filters: list[str] | None = None,
) -> dict[str, Any]:
    missing_tools = Counter(
        tool
        for action in actions
        if action.get("status") == "missing-tools"
        for tool in action.get("missingTools", [])
    )
    environment_statuses = Counter(
        action.get("environmentStatus") or "unknown"
        for action in actions
        if action.get("status") == "blocked-by-environment"
    )
    environment_reasons = Counter(
        action.get("environmentReason") or "unknown"
        for action in actions
        if action.get("status") == "blocked-by-environment"
    )
    environment_next_steps = Counter(
        action.get("nextStep")
        for action in actions
        if action.get("status") == "blocked-by-environment" and action.get("nextStep")
    )
    return {
        "missingTools": [
            {
                "tool": item["value"],
                "actions": item["actions"],
                "worklistCommand": blocker_worklist_command(
                    "missing-tools",
                    "--missing-tool",
                    item["value"],
                    evidence_dir=evidence_dir,
                    version_filters=version_filters,
                ),
            }
            for item in sorted_counts(missing_tools)
        ],
        "environment": [
            {
                "status": item["value"],
                "actions": item["actions"],
                "worklistCommand": blocker_worklist_command(
                    "blocked-by-environment",
                    "--environment-status",
                    item["value"],
                    evidence_dir=evidence_dir,
                    version_filters=version_filters,
                ),
            }
            for item in sorted_counts(environment_statuses)
        ],
        "environmentReasons": [
            {
                "reason": item["value"],
                "actions": item["actions"],
                "worklistCommand": blocker_worklist_command(
                    "blocked-by-environment",
                    "--environment-reason",
                    item["value"],
                    evidence_dir=evidence_dir,
                    version_filters=version_filters,
                ),
            }
            for item in sorted_counts(environment_reasons)
        ],
        "environmentNextSteps": [
            {"nextStep": item["value"], "actions": item["actions"]}
            for item in sorted_counts(environment_next_steps)
        ],
    }


def unprepared_evidence_status(evidence_dir: Path, output_dir: Path, plan: dict[str, Any]) -> dict[str, Any]:
    gates = plan.get("gates", [])
    return {
        "schemaVersion": "kube-actuary.release-evidence-status.v1",
        "evidenceDir": str(evidence_dir),
        "outputDir": str(output_dir),
        "summary": {
            "status": "not-prepared",
            "liveReports": 0,
            "supplementalEvidence": 0,
            "coveredGates": 0,
            "uncoveredGates": len(gates),
            "totalGates": len(gates),
            "coverageErrors": 0,
        },
        "nextTask": None,
        "nextTaskRun": None,
        "environmentProbe": None,
        "environmentBlockers": None,
        "versionIterationAdvance": None,
        "liveReports": [],
        "supplementalEvidence": [],
        "missing": {
            "coverage": ["evidence directory is not prepared"],
            "externalGates": [
                {
                    "id": gate.get("id"),
                    "item": gate.get("item"),
                    "kind": gate.get("kind"),
                    "reason": "evidence directory is not prepared",
                }
                for gate in gates
            ],
        },
        "nextCommands": [
            f"python3 -B scripts/prepare_live_evidence_directory.py {evidence_dir}",
            f"python3 -B scripts/prepare_live_evidence_directory.py {evidence_dir} --probe-environment",
            f"python3 -B scripts/inspect_release_evidence_directory.py {evidence_dir}",
        ],
    }


def build_progress(
    evidence_dir: Path | None = None,
    output_dir: Path | None = None,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
    version_filters: list[str] | None = None,
) -> dict[str, Any]:
    version_filters = list(version_filters or [])
    rows = filter_rows(taskboard_rows(TASKBOARD.read_text()), version_filters)
    plan = filter_gate_plan(build_plan(), version_filters)
    readiness = build_readiness_report(probe_environment=probe_environment, kubectl=kubectl)
    report: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "source": str(TASKBOARD.relative_to(ROOT)),
        "filters": {
            "versions": version_filters,
            "probeEnvironment": probe_environment,
            "kubectl": kubectl,
            "evidenceDir": evidence_dir.as_posix() if evidence_dir else None,
        },
        "releaseSuite": {
            "version": "0.2.0",
            "checks": len(COMMON_CHECKS),
        },
        "summary": {
            **count_statuses(rows),
            "rows": len(rows),
        },
        "versions": group_rows(rows),
        "externalGatePlan": summarize_gate_plan(plan),
        "liveValidationReadiness": summarize_readiness(readiness),
        "nextActions": build_next_actions(plan, readiness, version_filters=version_filters),
    }
    if evidence_dir is not None:
        target_output = output_dir if output_dir is not None else evidence_dir / DEFAULT_OUTPUT_DIR
        if evidence_dir.is_dir():
            live_queue = load_live_validation_queue(evidence_dir)
            if live_queue is not None:
                report["liveValidationQueue"] = {
                    "schemaVersion": live_queue.get("schemaVersion"),
                    "mode": live_queue.get("mode"),
                    "clusterWrites": live_queue.get("clusterWrites"),
                    "summary": live_queue.get("summary", {}),
                }
                report["nextActions"] = next_actions_from_queue(
                    live_queue,
                    evidence_dir=evidence_dir,
                    version_filters=version_filters,
                )
            report["evidenceStatus"] = inspect_directory(
                evidence_dir,
                target_output,
                version_filters=version_filters,
            )
        else:
            report["evidenceStatus"] = unprepared_evidence_status(evidence_dir, target_output, plan)
    return report


def render_markdown(progress: dict[str, Any]) -> str:
    summary = progress["summary"]
    lines = [
        "# KubeActuary Release Progress",
        "",
        f"Schema: `{progress['schemaVersion']}`",
        f"Source: `{progress['source']}`",
        "",
        "## Summary",
        "",
        f"- rows: {summary['rows']}",
        f"- done: {summary['done']}",
        f"- verify: {summary['verify']}",
        f"- doing: {summary['doing']}",
        f"- todo: {summary['todo']}",
        f"- release checks: {progress['releaseSuite']['checks']}",
        "",
    ]
    filters = progress.get("filters", {})
    if filters.get("versions"):
        lines.extend(["## Filters", "", f"- versions: `{', '.join(filters['versions'])}`", ""])
    lines.extend(["## Versions", ""])
    for group in progress["versions"]:
        counts = group["summary"]
        lines.append(
            f"- `{group['version']}` done={counts['done']} verify={counts['verify']} doing={counts['doing']} todo={counts['todo']}"
        )
        for item in group["openItems"]:
            lines.append(f"  - {item['status']}: {item['item']}")
    readiness = progress["liveValidationReadiness"]["summary"]
    next_action_source = progress["nextActions"].get("source")
    next_actions = progress["nextActions"]["summary"]
    lines.extend(
        [
            "",
            "## Live Readiness",
            "",
            f"- readiness-mode: `{progress['liveValidationReadiness'].get('mode')}`",
            f"- tool-ready-gates: {readiness['toolReadyGates']}/{readiness['liveGates']}",
            f"- tools: {readiness['toolsAvailable']}/{readiness['toolsTotal']} available",
            f"- next-action-source: `{next_action_source}`",
            f"- tool-ready-actions: {next_actions['toolReady']}/{next_actions['total']}",
            f"- tool-blocked-actions: {next_actions.get('blockedByTools', 0)}",
            f"- environment-blocked-actions: {next_actions.get('blockedByEnvironment', 0)}",
        ]
    )
    readiness_probe = progress["liveValidationReadiness"].get("environmentProbe")
    if isinstance(readiness_probe, dict):
        lines.append(f"- environment-probe: `{readiness_probe.get('clusterAccess')}`")
        lines.append(f"- environment-reason: `{readiness_probe.get('reason')}`")
    tool_ready_actions = [action for action in progress["nextActions"]["actions"] if action["status"] == "tool-ready"]
    blockers = progress["nextActions"].get("blockers", {})
    missing_tool_blockers = blockers.get("missingTools") or []
    environment_blockers = blockers.get("environment") or []
    environment_reason_blockers = blockers.get("environmentReasons") or []
    environment_next_steps = blockers.get("environmentNextSteps") or []
    if missing_tool_blockers or environment_blockers or environment_reason_blockers:
        lines.extend(["", "## Action Blockers", ""])
        for item in missing_tool_blockers:
            lines.append(f"- missing-tool-blocker: `{item['tool']}` ({item['actions']} actions)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in environment_blockers:
            lines.append(f"- environment-blocker: `{item['status']}` ({item['actions']} actions)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in environment_reason_blockers:
            lines.append(f"- environment-reason-blocker: `{item['reason']}` ({item['actions']} actions)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in environment_next_steps:
            lines.append(f"- blocker-next-step: {item['nextStep']} ({item['actions']} actions)")
    if tool_ready_actions:
        lines.extend(["", "## Tool-Ready Actions", ""])
        for action in tool_ready_actions:
            lines.append(f"- `{action['id']}` {action['item']}")
            if action["firstCommand"]:
                lines.append(f"  - `{action['firstCommand']}`")
    if "evidenceStatus" in progress:
        status = progress["evidenceStatus"]["summary"]
        lines.extend(
            [
                "",
                "## Evidence Directory",
                "",
                f"- status: {status['status']}",
                f"- covered: {status['coveredGates']}/{status['totalGates']}",
                f"- live reports: {status['liveReports']}",
                f"- supplemental: {status['supplementalEvidence']}",
            ]
        )
        evidence_status = progress["evidenceStatus"]
        next_task = evidence_status.get("nextTask")
        selected = next_task.get("selected", {}) if isinstance(next_task, dict) else {}
        if selected.get("id"):
            lines.append(f"- next-task: `{selected.get('id')}` ({selected.get('captureStatus')})")
            if next_task.get("queueSource"):
                lines.append(f"- next-task-queue-source: `{next_task.get('queueSource')}`")
            if next_task.get("queueSourceOrigin"):
                lines.append(f"- next-task-queue-source-origin: `{next_task.get('queueSourceOrigin')}`")
            consistency = next_task.get("queueConsistency") or {}
            if consistency.get("status"):
                lines.append(f"- next-task-queue-consistency: `{consistency.get('status')}`")
                if consistency.get("mismatches"):
                    lines.append(f"- next-task-queue-mismatches: `{', '.join(consistency.get('mismatches', []))}`")
            file_summary = next_task.get("summary", {}) if isinstance(next_task, dict) else {}
            if file_summary:
                lines.append(f"- next-task-files: {file_summary.get('existingFiles', 0)}/{file_summary.get('files', 0)}")
            for item in selected.get("files", []):
                file_status = "present" if item.get("exists") else "missing"
                lines.append(f"- next-task-file: `{file_status}` `{item.get('role')}` `{item.get('path')}`")
            for command in selected.get("resolvedCommands", []):
                lines.append(f"- next-task-command: `{command}`")
        next_task_run = evidence_status.get("nextTaskRun")
        if isinstance(next_task_run, dict):
            lines.append(f"- next-task-run: `{next_task_run.get('status')}` ({next_task_run.get('mode')})")
            if next_task_run.get("queueSource"):
                lines.append(f"- next-task-run-queue-source: `{next_task_run.get('queueSource')}`")
            if next_task_run.get("queueSourceOrigin"):
                lines.append(f"- next-task-run-queue-source-origin: `{next_task_run.get('queueSourceOrigin')}`")
            consistency = next_task_run.get("nextTaskConsistency") or {}
            if consistency.get("status"):
                lines.append(f"- next-task-run-consistency: `{consistency.get('status')}`")
                if consistency.get("mismatches"):
                    lines.append(f"- next-task-run-mismatches: `{', '.join(consistency.get('mismatches', []))}`")
            failure = next_task_run.get("failure")
            if isinstance(failure, dict) and failure.get("message"):
                lines.append(f"- next-task-run-error: `{failure.get('message')}`")
        environment_probe = evidence_status.get("environmentProbe")
        if isinstance(environment_probe, dict):
            lines.append(f"- environment-probe: `{environment_probe.get('clusterAccess')}`")
        environment_blockers = evidence_status.get("environmentBlockers")
        if isinstance(environment_blockers, dict):
            blocker_summary = environment_blockers.get("summary", {})
            lines.append(f"- environment-blockers: {blocker_summary.get('blockedByEnvironment', 0)}")
            selected_blocker = environment_blockers.get("selected") or {}
            if selected_blocker.get("nextStep"):
                lines.append(f"- environment-next: {selected_blocker.get('nextStep')}")
        advance = evidence_status.get("versionIterationAdvance")
        if isinstance(advance, dict):
            lines.append(f"- version-iteration-advance: `{advance.get('status')}`")
            if advance.get("runId"):
                lines.append(f"- version-iteration-advance-run-id: `{advance.get('runId')}`")
            history = advance.get("history", {})
            if isinstance(history, dict) and history.get("runs") is not None:
                lines.append(f"- version-iteration-advance-history-runs: {history.get('runs')}")
            if advance.get("queueSource"):
                lines.append(f"- version-iteration-advance-queue-source: `{advance.get('queueSource')}`")
            if advance.get("queueSourceOrigin"):
                lines.append(f"- version-iteration-advance-queue-source-origin: `{advance.get('queueSourceOrigin')}`")
            consistency = advance.get("nextTaskConsistency") or {}
            if consistency.get("status"):
                lines.append(f"- version-iteration-advance-consistency: `{consistency.get('status')}`")
                if consistency.get("mismatches"):
                    lines.append(f"- version-iteration-advance-mismatches: `{', '.join(consistency.get('mismatches', []))}`")
        next_commands = evidence_status.get("nextCommands", [])
        for command in next_commands:
            lines.append(f"- next: `{command}`")
    lines.extend(["", "## Closure", ""])
    for command in progress["externalGatePlan"]["closureCommands"]:
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def render_text(progress: dict[str, Any]) -> str:
    summary = progress["summary"]
    lines = [
        f"schema: {progress['schemaVersion']}",
        f"source: {progress['source']}",
        f"rows: {summary['rows']}",
        f"done: {summary['done']}",
        f"verify: {summary['verify']}",
        f"doing: {summary['doing']}",
        f"todo: {summary['todo']}",
        f"release-checks: {progress['releaseSuite']['checks']}",
    ]
    filters = progress.get("filters", {})
    for version in filters.get("versions", []):
        lines.append(f"filter-version: {version}")
    if filters.get("evidenceDir"):
        lines.append(f"evidence-dir: {filters['evidenceDir']}")

    for group in progress["versions"]:
        counts = group["summary"]
        lines.append(
            f"version: {group['version']} done={counts['done']} verify={counts['verify']} "
            f"doing={counts['doing']} todo={counts['todo']}"
        )
        for item in group["openItems"]:
            lines.append(f"item: {group['version']} {item['status']} {item['item']}")

    readiness = progress["liveValidationReadiness"]["summary"]
    next_actions = progress["nextActions"]
    next_action_summary = next_actions["summary"]
    lines.extend(
        [
            f"readiness-mode: {progress['liveValidationReadiness'].get('mode')}",
            f"tool-ready-gates: {readiness['toolReadyGates']}/{readiness['liveGates']}",
            f"tools: {readiness['toolsAvailable']}/{readiness['toolsTotal']}",
            f"next-action-source: {next_actions.get('source')}",
            f"tool-ready-actions: {next_action_summary['toolReady']}/{next_action_summary['total']}",
            f"tool-blocked-actions: {next_action_summary.get('blockedByTools', 0)}",
            f"environment-blocked-actions: {next_action_summary.get('blockedByEnvironment', 0)}",
        ]
    )
    readiness_probe = progress["liveValidationReadiness"].get("environmentProbe")
    if isinstance(readiness_probe, dict):
        lines.append(f"environment-probe: {readiness_probe.get('clusterAccess')}")
        lines.append(f"environment-reason: {readiness_probe.get('reason')}")

    blockers = next_actions.get("blockers", {})
    for item in blockers.get("missingTools") or []:
        lines.append(f"missing-tool-blocker: {item['tool']} actions={item['actions']}")
        if item.get("worklistCommand"):
            lines.append(f"blocker-worklist: {item['worklistCommand']}")
    for item in blockers.get("environment") or []:
        lines.append(f"environment-blocker: {item['status']} actions={item['actions']}")
        if item.get("worklistCommand"):
            lines.append(f"blocker-worklist: {item['worklistCommand']}")
    for item in blockers.get("environmentReasons") or []:
        lines.append(f"environment-reason-blocker: {item['reason']} actions={item['actions']}")
        if item.get("worklistCommand"):
            lines.append(f"blocker-worklist: {item['worklistCommand']}")
    for item in blockers.get("environmentNextSteps") or []:
        lines.append(f"blocker-next-step: {item['nextStep']} actions={item['actions']}")

    for action in next_actions["actions"]:
        lines.append(f"action: {action.get('id')} {action.get('status')} {action.get('version')} {action.get('item')}")
        if action.get("environmentStatus"):
            lines.append(f"action-environment: {action.get('environmentStatus')}")
        if action.get("environmentReason"):
            lines.append(f"action-environment-reason: {action.get('environmentReason')}")
        if action.get("firstCommand"):
            lines.append(f"first-command: {action['firstCommand']}")

    if "evidenceStatus" in progress:
        evidence_status = progress["evidenceStatus"]
        status = evidence_status["summary"]
        lines.extend(
            [
                f"evidence-status: {status['status']}",
                f"evidence-covered: {status['coveredGates']}/{status['totalGates']}",
                f"evidence-live-reports: {status['liveReports']}",
                f"evidence-supplemental: {status['supplementalEvidence']}",
            ]
        )
        next_task = evidence_status.get("nextTask")
        selected = next_task.get("selected", {}) if isinstance(next_task, dict) else {}
        if selected.get("id"):
            lines.append(f"next-task: {selected.get('id')} {selected.get('captureStatus')}")
            if next_task.get("queueSource"):
                lines.append(f"next-task-queue-source: {next_task.get('queueSource')}")
            if next_task.get("queueSourceOrigin"):
                lines.append(f"next-task-queue-source-origin: {next_task.get('queueSourceOrigin')}")
            consistency = next_task.get("queueConsistency") or {}
            if consistency.get("status"):
                lines.append(f"next-task-queue-consistency: {consistency.get('status')}")
            for item in selected.get("files", []):
                file_status = "present" if item.get("exists") else "missing"
                lines.append(f"next-task-file: {file_status} {item.get('role')} {item.get('path')}")
            for command in selected.get("resolvedCommands", []):
                lines.append(f"next-task-command: {command}")
        next_task_run = evidence_status.get("nextTaskRun")
        if isinstance(next_task_run, dict):
            lines.append(f"next-task-run: {next_task_run.get('status')} {next_task_run.get('mode')}")
            failure = next_task_run.get("failure")
            if isinstance(failure, dict) and failure.get("message"):
                lines.append(f"next-task-run-error: {failure.get('message')}")
        environment_probe = evidence_status.get("environmentProbe")
        if isinstance(environment_probe, dict):
            lines.append(f"evidence-environment-probe: {environment_probe.get('clusterAccess')}")
        environment_blockers = evidence_status.get("environmentBlockers")
        if isinstance(environment_blockers, dict):
            blocker_summary = environment_blockers.get("summary", {})
            lines.append(f"evidence-environment-blockers: {blocker_summary.get('blockedByEnvironment', 0)}")
            selected_blocker = environment_blockers.get("selected") or {}
            if selected_blocker.get("nextStep"):
                lines.append(f"evidence-environment-next: {selected_blocker.get('nextStep')}")
        advance = evidence_status.get("versionIterationAdvance")
        if isinstance(advance, dict):
            lines.append(f"version-iteration-advance: {advance.get('status')}")
            if advance.get("runId"):
                lines.append(f"version-iteration-advance-run-id: {advance.get('runId')}")
        for command in evidence_status.get("nextCommands", []):
            lines.append(f"next: {command}")

    for command in progress["externalGatePlan"]["closureCommands"]:
        lines.append(f"closure-command: {command}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary release progress report.")
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="json")
    parser.add_argument("--version", action="append", default=[], help="filter to a release version; repeatable")
    parser.add_argument("--evidence-dir", help="optional local evidence directory to inspect")
    parser.add_argument("--output-dir", help="artifact output directory for evidence-dir status")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    try:
        evidence_dir = Path(args.evidence_dir) if args.evidence_dir else None
        output_dir = Path(args.output_dir) if args.output_dir else None
        progress = build_progress(
            evidence_dir,
            output_dir,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
            version_filters=args.version,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("release-progress: failed")
        print(f"error: {exc}")
        return 1

    if args.format == "json":
        rendered = json.dumps(progress, indent=2, sort_keys=True) + "\n"
    elif args.format == "markdown":
        rendered = render_markdown(progress)
    else:
        rendered = render_text(progress)

    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"release-progress: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
