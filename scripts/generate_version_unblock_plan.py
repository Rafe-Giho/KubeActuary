#!/usr/bin/env python3
"""Generate a local plan for unblocking version evidence work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_version_worklist import command_string  # noqa: E402
from scripts.record_version_blockers import build_ledger  # noqa: E402


SCHEMA_VERSION = "kube-actuary.version-unblock-plan.v1"
RECORD_JSON = "version-unblock-plan.json"
RECORD_MD = "version-unblock-plan.md"
TOOL_CHECK_COMMANDS = {
    "az": ["az", "version"],
    "gcloud": ["gcloud", "version"],
    "helm": ["helm", "version"],
    "k3s": ["k3s", "--version"],
    "kind": ["kind", "version"],
    "kubectl": ["kubectl", "version", "--client=true"],
    "kubectl-krew": ["kubectl", "krew", "version"],
    "microk8s": ["microk8s", "version"],
    "minikube": ["minikube", "version"],
}


def add_repeated(args: list[str], flag: str, values: list[Any]) -> None:
    for value in values:
        args.extend([flag, str(value)])


def filtered_args(filters: dict[str, Any]) -> list[str]:
    args: list[str] = []
    add_repeated(args, "--version", filters.get("versions") or [])
    add_repeated(args, "--capture-status", filters.get("captureStatuses") or [])
    add_repeated(args, "--missing-tool", filters.get("missingTools") or [])
    add_repeated(args, "--environment-status", filters.get("environmentStatuses") or [])
    add_repeated(args, "--environment-reason", filters.get("environmentReasons") or [])
    if filters.get("probeEnvironment"):
        args.append("--probe-environment")
    if filters.get("kubectl") and filters.get("kubectl") != "kubectl":
        args.extend(["--kubectl", str(filters["kubectl"])])
    return args


def base_recorder_args(script: str, filters: dict[str, Any], record: bool = False) -> list[str]:
    args = ["python3", "-B", f"scripts/{script}"]
    if record:
        args.append("--record")
    if filters.get("evidenceDir"):
        args.extend(["--evidence-dir", str(filters["evidenceDir"])])
    if filters.get("historyDir"):
        args.extend(["--history-dir", str(filters["historyDir"])])
    args.extend(filtered_args(filters))
    return args


def refresh_command(filters: dict[str, Any]) -> str | None:
    evidence_dir = filters.get("evidenceDir")
    if not evidence_dir:
        return None
    args = ["python3", "-B", "scripts/prepare_live_evidence_directory.py", str(evidence_dir), "--probe-environment"]
    if filters.get("kubectl") and filters.get("kubectl") != "kubectl":
        args.extend(["--kubectl", str(filters["kubectl"])])
    return command_string(args)


def blocker_record_command(filters: dict[str, Any]) -> str:
    return command_string(base_recorder_args("record_version_blockers.py", filters, record=True))


def unblock_record_command(filters: dict[str, Any]) -> str:
    return command_string(base_recorder_args("generate_version_unblock_plan.py", filters, record=True))


def scoped_filters(filters: dict[str, Any], **updates: Any) -> dict[str, Any]:
    scoped = dict(filters)
    for key, value in updates.items():
        scoped[key] = value
    return scoped


def action_commands(filters: dict[str, Any], worklist_command: str | None) -> dict[str, list[str]]:
    refresh = refresh_command(filters)
    commands = {
        "verify": [],
        "refresh": [command for command in [refresh] if command],
        "inspect": [],
        "record": [
            blocker_record_command(filters),
            unblock_record_command(filters),
        ],
    }
    if worklist_command:
        commands["inspect"].append(worklist_command)
    return commands


def missing_tool_action(item: dict[str, Any], filters: dict[str, Any], index: int) -> dict[str, Any]:
    tool = str(item.get("tool"))
    scoped = scoped_filters(
        filters,
        captureStatuses=["missing-tools"],
        missingTools=[tool],
        environmentStatuses=[],
        environmentReasons=[],
    )
    commands = action_commands(scoped, item.get("worklistCommand"))
    commands["verify"].insert(0, command_string(TOOL_CHECK_COMMANDS.get(tool, ["command", "-v", tool])))
    return {
        "id": f"{index:02d}-missing-tool-{tool}",
        "kind": "missing-tool",
        "status": "blocked",
        "tool": tool,
        "items": item.get("items", 0),
        "affectedVersions": item.get("versions", []),
        "nextStep": "install the missing tool or run the evidence capture on a host that already has it",
        "commands": commands,
    }


def environment_action(item: dict[str, Any], reason: str | None, filters: dict[str, Any], index: int) -> dict[str, Any]:
    status = str(item.get("status"))
    scoped = scoped_filters(
        filters,
        captureStatuses=["blocked-by-environment"],
        missingTools=[],
        environmentStatuses=[status],
        environmentReasons=[reason] if reason else [],
    )
    commands = action_commands(scoped, item.get("worklistCommand"))
    kubectl = str(filters.get("kubectl") or "kubectl")
    commands["verify"].insert(0, command_string([kubectl, "cluster-info", "--request-timeout=5s"]))
    return {
        "id": f"{index:02d}-environment-{status}",
        "kind": "environment",
        "status": "blocked",
        "environmentStatus": status,
        "environmentReason": reason,
        "items": item.get("items", 0),
        "affectedVersions": item.get("versions", []),
        "nextStep": "start or select a disposable cluster, then rerun the probe",
        "commands": commands,
    }


def reason_by_environment_status(ledger: dict[str, Any]) -> dict[str, str]:
    reasons = ledger.get("blockers", {}).get("environmentReasons") or []
    if not reasons:
        return {}
    # Current ledgers expose one environment status group. Keep this deterministic
    # and conservative when more groups are added.
    status_groups = ledger.get("blockers", {}).get("environment") or []
    if len(status_groups) != 1:
        return {}
    reason = reasons[0].get("reason") if len(reasons) == 1 else None
    return {str(status_groups[0].get("status")): str(reason)} if reason else {}


def build_plan(
    version_filters: list[str] | None = None,
    evidence_dir: Path | None = None,
    history_dir: Path | None = None,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
    environment_reason_filters: list[str] | None = None,
) -> dict[str, Any]:
    ledger = build_ledger(
        version_filters=version_filters,
        evidence_dir=evidence_dir,
        history_dir=history_dir,
        probe_environment=probe_environment,
        kubectl=kubectl,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
        environment_reason_filters=environment_reason_filters,
    )
    filters = ledger.get("filters", {})
    actions: list[dict[str, Any]] = []
    index = 1
    for item in ledger.get("blockers", {}).get("missingTools") or []:
        actions.append(missing_tool_action(item, filters, index))
        index += 1
    environment_reasons = reason_by_environment_status(ledger)
    for item in ledger.get("blockers", {}).get("environment") or []:
        actions.append(environment_action(item, environment_reasons.get(str(item.get("status"))), filters, index))
        index += 1
    summary = ledger.get("summary", {})
    plan = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceBlockerSchema": ledger.get("schemaVersion"),
        "sourceWorklistQueueSource": ledger.get("sourceWorklistQueueSource"),
        "source": ledger.get("source"),
        "status": "blocked" if actions else "clear",
        "clusterWrites": "disabled",
        "evidenceDir": ledger.get("evidenceDir"),
        "filters": filters,
        "summary": {
            "actions": len(actions),
            "missingToolActions": sum(1 for action in actions if action.get("kind") == "missing-tool"),
            "environmentActions": sum(1 for action in actions if action.get("kind") == "environment"),
            "blockedItems": summary.get("blockedItems", 0),
            "affectedVersions": summary.get("affectedVersions", 0),
            "evidenceFiles": summary.get("evidenceFiles", 0),
            "existingEvidenceFiles": summary.get("existingEvidenceFiles", 0),
        },
        "actions": actions,
        "nextCommands": {
            "recordBlockers": blocker_record_command(filters),
            "recordUnblockPlan": unblock_record_command(filters),
        },
    }
    if ledger.get("historyStatus"):
        plan["historyStatus"] = ledger["historyStatus"]
    if ledger.get("environmentProbe"):
        plan["environmentProbe"] = ledger["environmentProbe"]
    return plan


def render_action_commands(action: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    commands = action.get("commands") or {}
    for label in ("verify", "refresh", "inspect", "record"):
        for command in commands.get(label) or []:
            lines.append(f"    {label}: `{command}`")
    return lines


def render_markdown(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        "# KubeActuary Version Unblock Plan",
        "",
        f"Schema: `{plan['schemaVersion']}`",
        f"Blocker schema: `{plan.get('sourceBlockerSchema')}`",
        f"Queue source: `{plan.get('sourceWorklistQueueSource') or 'generated'}`",
        f"Status: `{plan['status']}`",
        f"Cluster writes: `{plan['clusterWrites']}`",
        "",
        "## Summary",
        "",
        f"- actions: {summary['actions']}",
        f"- missing-tool actions: {summary['missingToolActions']}",
        f"- environment actions: {summary['environmentActions']}",
        f"- blocked items: {summary['blockedItems']}",
        f"- affected versions: {summary['affectedVersions']}",
        f"- evidence files: {summary['existingEvidenceFiles']}/{summary['evidenceFiles']}",
        "",
        "## Actions",
        "",
    ]
    if not plan.get("actions"):
        lines.append("- none")
    for action in plan.get("actions", []):
        versions = ", ".join(action.get("affectedVersions") or ["none"])
        target = action.get("tool") or action.get("environmentStatus")
        lines.append(f"- `{action['id']}` {action['kind']} `{target}` ({action['items']} items)")
        if action.get("environmentReason"):
            lines.append(f"    reason: `{action['environmentReason']}`")
        lines.append(f"    versions: `{versions}`")
        lines.append(f"    next: {action.get('nextStep')}")
        lines.extend(render_action_commands(action))
    lines.extend(["", "## Next Local Loop", ""])
    for label, command in plan.get("nextCommands", {}).items():
        lines.append(f"- {label}: `{command}`")
    return "\n".join(lines) + "\n"


def render_text(plan: dict[str, Any]) -> str:
    summary = plan["summary"]
    lines = [
        f"schema: {plan['schemaVersion']}",
        f"queue-source: {plan.get('sourceWorklistQueueSource') or 'generated'}",
        f"status: {plan['status']}",
        f"cluster-writes: {plan['clusterWrites']}",
        f"actions: {summary['actions']}",
        f"missing-tool-actions: {summary['missingToolActions']}",
        f"environment-actions: {summary['environmentActions']}",
        f"blocked-items: {summary['blockedItems']}",
        f"affected-versions: {summary['affectedVersions']}",
        f"evidence-files: {summary['existingEvidenceFiles']}/{summary['evidenceFiles']}",
    ]
    for action in plan.get("actions", []):
        target = action.get("tool") or action.get("environmentStatus")
        versions = ", ".join(action.get("affectedVersions") or ["none"])
        lines.append(f"action: {action['id']} {action['kind']} {target} ({action['items']} items)")
        if action.get("environmentReason"):
            lines.append(f"reason: {action['environmentReason']}")
        lines.append(f"versions: {versions}")
        lines.append(f"next: {action.get('nextStep')}")
        commands = action.get("commands") or {}
        for label in ("verify", "refresh", "inspect", "record"):
            for command in commands.get(label) or []:
                lines.append(f"{label}: {command}")
    for label, command in plan.get("nextCommands", {}).items():
        lines.append(f"next-command: {label}: {command}")
    return "\n".join(lines) + "\n"


def render_payload(plan: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if fmt == "markdown":
        return render_markdown(plan)
    return render_text(plan)


def record_plan(plan: dict[str, Any], evidence_dir: Path | None, record_dir: Path | None) -> dict[str, str]:
    target = record_dir
    if target is None:
        if evidence_dir is None:
            raise ValueError("--record requires --evidence-dir or --record-dir")
        target = evidence_dir / ".kubeactuary"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / RECORD_JSON
    md_path = target / RECORD_MD
    json_path.write_text(render_payload(plan, "json"))
    md_path.write_text(render_payload(plan, "markdown"))
    return {"json": json_path.as_posix(), "markdown": md_path.as_posix()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary version unblock plan.")
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="json")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    parser.add_argument("--record", action="store_true", help="write version-unblock-plan JSON and Markdown metadata")
    parser.add_argument("--record-dir", help="metadata directory for --record")
    parser.add_argument("--version", action="append", default=[], help="filter to a release version; repeatable")
    parser.add_argument("--capture-status", action="append", default=[], help="filter open items by capture status; repeatable")
    parser.add_argument("--missing-tool", action="append", default=[], help="filter open items by missing tool; repeatable")
    parser.add_argument("--environment-status", action="append", default=[], help="filter open items by environment status; repeatable")
    parser.add_argument("--environment-reason", action="append", default=[], help="filter open items by environment reason; repeatable")
    parser.add_argument("--evidence-dir", help="optional evidence directory for prepared queue and file readiness")
    parser.add_argument("--history-dir", help="optional version iteration history directory for repeated blocker context")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else None
    record_dir = Path(args.record_dir) if args.record_dir else None
    try:
        plan = build_plan(
            version_filters=args.version,
            evidence_dir=evidence_dir,
            history_dir=Path(args.history_dir) if args.history_dir else None,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
            capture_status_filters=args.capture_status,
            missing_tool_filters=args.missing_tool,
            environment_status_filters=args.environment_status,
            environment_reason_filters=args.environment_reason,
        )
        record_paths = record_plan(plan, evidence_dir, record_dir) if args.record else None
    except ValueError as exc:
        print("version-unblock-plan: failed", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rendered = render_payload(plan, args.format)
    if args.output == "-":
        print(rendered, end="")
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        print(f"version-unblock-plan: wrote {args.output}")
    if record_paths and args.output != "-":
        print(f"version-unblock-plan: recorded {record_paths['json']}")
        print(f"version-unblock-plan: recorded {record_paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
