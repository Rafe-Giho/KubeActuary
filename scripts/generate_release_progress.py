#!/usr/bin/env python3
"""Generate a versioned release progress report from local state."""

from __future__ import annotations

import argparse
import json
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
    return {
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


def build_next_actions(plan: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
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
        commands = gate.get("recommendedCommands") or []
        actions.append(
            {
                "id": gate.get("id"),
                "item": gate.get("item"),
                "kind": gate.get("kind"),
                "version": gate.get("version") or gate.get("section"),
                "status": "tool-ready" if not missing_tools else "missing-tools",
                "missingTools": missing_tools,
                "firstCommand": commands[0] if commands else None,
            }
        )
    tool_ready = sum(1 for action in actions if action["status"] == "tool-ready")
    return {
        "source": "live-readiness-inventory",
        "summary": {
            "total": len(actions),
            "toolReady": tool_ready,
            "blockedByTools": len(actions) - tool_ready,
            "blockedByEnvironment": 0,
        },
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


def next_actions_from_queue(queue: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for item in queue.get("items", []):
        if not isinstance(item, dict):
            continue
        commands = item.get("resolvedCommands") or item.get("commands") or []
        actions.append(
            {
                "id": item.get("id"),
                "item": item.get("item"),
                "kind": item.get("kind"),
                "version": item.get("version"),
                "status": item.get("status"),
                "missingTools": item.get("missingTools", []),
                "environmentStatus": item.get("environmentStatus"),
                "nextStep": item.get("nextStep"),
                "firstCommand": commands[0] if commands else None,
            }
        )
    summary = queue.get("summary", {})
    return {
        "source": "prepared-live-validation-queue",
        "summary": {
            "total": summary.get("total", len(actions)),
            "toolReady": summary.get("toolReady", 0),
            "blockedByTools": summary.get("blockedByTools", 0),
            "blockedByEnvironment": summary.get("blockedByEnvironment", 0),
        },
        "actions": actions,
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


def build_progress(evidence_dir: Path | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    rows = taskboard_rows(TASKBOARD.read_text())
    plan = build_plan()
    readiness = build_readiness_report()
    report: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "source": str(TASKBOARD.relative_to(ROOT)),
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
        "nextActions": build_next_actions(plan, readiness),
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
                report["nextActions"] = next_actions_from_queue(live_queue)
            report["evidenceStatus"] = inspect_directory(evidence_dir, target_output)
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
        "## Versions",
        "",
    ]
    for group in progress["versions"]:
        counts = group["summary"]
        lines.append(
            f"- `{group['version']}` done={counts['done']} verify={counts['verify']} doing={counts['doing']} todo={counts['todo']}"
        )
        for item in group["openItems"][:3]:
            lines.append(f"  - {item['status']}: {item['item']}")
    readiness = progress["liveValidationReadiness"]["summary"]
    next_action_source = progress["nextActions"].get("source")
    next_actions = progress["nextActions"]["summary"]
    lines.extend(
        [
            "",
            "## Live Readiness",
            "",
            f"- tool-ready-gates: {readiness['toolReadyGates']}/{readiness['liveGates']}",
            f"- tools: {readiness['toolsAvailable']}/{readiness['toolsTotal']} available",
            f"- next-action-source: `{next_action_source}`",
            f"- tool-ready-actions: {next_actions['toolReady']}/{next_actions['total']}",
            f"- tool-blocked-actions: {next_actions.get('blockedByTools', 0)}",
            f"- environment-blocked-actions: {next_actions.get('blockedByEnvironment', 0)}",
        ]
    )
    tool_ready_actions = [action for action in progress["nextActions"]["actions"] if action["status"] == "tool-ready"]
    if tool_ready_actions:
        lines.extend(["", "## Tool-Ready Actions", ""])
        for action in tool_ready_actions[:5]:
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
        next_task_run = evidence_status.get("nextTaskRun")
        if isinstance(next_task_run, dict):
            lines.append(f"- next-task-run: `{next_task_run.get('status')}` ({next_task_run.get('mode')})")
            if next_task_run.get("queueSource"):
                lines.append(f"- next-task-run-queue-source: `{next_task_run.get('queueSource')}`")
            if next_task_run.get("queueSourceOrigin"):
                lines.append(f"- next-task-run-queue-source-origin: `{next_task_run.get('queueSourceOrigin')}`")
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
            if advance.get("queueSource"):
                lines.append(f"- version-iteration-advance-queue-source: `{advance.get('queueSource')}`")
            if advance.get("queueSourceOrigin"):
                lines.append(f"- version-iteration-advance-queue-source-origin: `{advance.get('queueSourceOrigin')}`")
        next_commands = evidence_status.get("nextCommands", [])
        for command in next_commands[:3]:
            lines.append(f"- next: `{command}`")
    lines.extend(["", "## Closure", ""])
    for command in progress["externalGatePlan"]["closureCommands"]:
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary release progress report.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--evidence-dir", help="optional local evidence directory to inspect")
    parser.add_argument("--output-dir", help="artifact output directory for evidence-dir status")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    try:
        evidence_dir = Path(args.evidence_dir) if args.evidence_dir else None
        output_dir = Path(args.output_dir) if args.output_dir else None
        progress = build_progress(evidence_dir, output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("release-progress: failed")
        print(f"error: {exc}")
        return 1

    if args.format == "json":
        rendered = json.dumps(progress, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_markdown(progress)

    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"release-progress: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
