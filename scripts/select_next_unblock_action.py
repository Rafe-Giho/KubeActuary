#!/usr/bin/env python3
"""Select the next local unblock action deterministically."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_version_unblock_plan import build_plan, render_action_commands  # noqa: E402


SCHEMA_VERSION = "kube-actuary.next-unblock-action.v1"
RECORD_JSON = "next-unblock-action.json"
RECORD_MD = "next-unblock-action.md"
SELECTION_POLICY = "highest-items-then-kind-target"
KIND_PRIORITY = {
    "missing-tool": 0,
    "environment": 1,
}


def action_target(action: dict[str, Any]) -> str:
    return str(action.get("tool") or action.get("environmentStatus") or action.get("id") or "unknown")


def action_sort_key(action: dict[str, Any]) -> tuple[int, int, str, str]:
    return (
        -int(action.get("items") or 0),
        KIND_PRIORITY.get(str(action.get("kind")), 99),
        action_target(action),
        str(action.get("id") or ""),
    )


def select_action(actions: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not actions:
        return None
    return sorted(actions, key=action_sort_key)[0]


def build_selection(
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
    plan = build_plan(
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
    actions = list(plan.get("actions") or [])
    selected = select_action(actions)
    summary = dict(plan.get("summary") or {})
    summary.update(
        {
            "candidateActions": len(actions),
            "selected": selected is not None,
            "selectedActionId": selected.get("id") if selected else None,
            "selectedKind": selected.get("kind") if selected else None,
            "selectedTarget": action_target(selected) if selected else None,
            "selectedItems": selected.get("items") if selected else 0,
        }
    )
    selection = {
        "schemaVersion": SCHEMA_VERSION,
        "sourcePlanSchema": plan.get("schemaVersion"),
        "sourceBlockerSchema": plan.get("sourceBlockerSchema"),
        "sourceWorklistQueueSource": plan.get("sourceWorklistQueueSource"),
        "source": plan.get("source"),
        "status": "selected" if selected else "clear",
        "planStatus": plan.get("status"),
        "clusterWrites": plan.get("clusterWrites"),
        "selectionPolicy": SELECTION_POLICY,
        "evidenceDir": plan.get("evidenceDir"),
        "filters": plan.get("filters", {}),
        "summary": summary,
        "selected": selected,
        "nextCommands": plan.get("nextCommands", {}),
    }
    if plan.get("environmentProbe"):
        selection["environmentProbe"] = plan["environmentProbe"]
    if plan.get("historyStatus"):
        selection["historyStatus"] = plan["historyStatus"]
    return selection


def render_text(selection: dict[str, Any]) -> str:
    summary = selection["summary"]
    selected = selection.get("selected")
    lines = [
        f"next-unblock-action: {selection['status']}",
        f"schema: {selection['schemaVersion']}",
        f"queue-source: {selection.get('sourceWorklistQueueSource') or 'generated'}",
        f"cluster-writes: {selection.get('clusterWrites')}",
        f"selection-policy: {selection.get('selectionPolicy')}",
        f"actions: {summary.get('candidateActions', 0)}",
        f"blocked-items: {summary.get('blockedItems', 0)}",
        f"affected-versions: {summary.get('affectedVersions', 0)}",
    ]
    if not selected:
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            f"action-id: {selected.get('id')}",
            f"kind: {selected.get('kind')}",
            f"target: {action_target(selected)}",
            f"action-items: {selected.get('items', 0)}",
            f"versions: {', '.join(selected.get('affectedVersions') or ['none'])}",
            f"next: {selected.get('nextStep')}",
        ]
    )
    if selected.get("environmentReason"):
        lines.append(f"reason: {selected.get('environmentReason')}")
    for label in ("verify", "refresh", "inspect", "record"):
        for command in (selected.get("commands") or {}).get(label) or []:
            lines.append(f"{label}: {command}")
    for label, command in selection.get("nextCommands", {}).items():
        lines.append(f"next-command: {label}: {command}")
    return "\n".join(lines) + "\n"


def render_markdown(selection: dict[str, Any]) -> str:
    summary = selection["summary"]
    selected = selection.get("selected")
    lines = [
        "# KubeActuary Next Unblock Action",
        "",
        f"Schema: `{selection['schemaVersion']}`",
        f"Plan schema: `{selection.get('sourcePlanSchema')}`",
        f"Queue source: `{selection.get('sourceWorklistQueueSource') or 'generated'}`",
        f"Status: `{selection['status']}`",
        f"Cluster writes: `{selection.get('clusterWrites')}`",
        f"Selection policy: `{selection.get('selectionPolicy')}`",
        "",
        "## Summary",
        "",
        f"- actions: {summary.get('candidateActions', 0)}",
        f"- blocked items: {summary.get('blockedItems', 0)}",
        f"- affected versions: {summary.get('affectedVersions', 0)}",
        "",
        "## Selected",
        "",
    ]
    if not selected:
        lines.append("- none")
    else:
        lines.append(
            f"- `{selected.get('id')}` {selected.get('kind')} "
            f"`{action_target(selected)}` ({selected.get('items', 0)} items)"
        )
        if selected.get("environmentReason"):
            lines.append(f"    reason: `{selected.get('environmentReason')}`")
        lines.append(f"    versions: `{', '.join(selected.get('affectedVersions') or ['none'])}`")
        lines.append(f"    next: {selected.get('nextStep')}")
        lines.extend(render_action_commands(selected))
    lines.extend(["", "## Next Local Loop", ""])
    for label, command in selection.get("nextCommands", {}).items():
        lines.append(f"- {label}: `{command}`")
    return "\n".join(lines) + "\n"


def render_payload(selection: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(selection, indent=2, sort_keys=True) + "\n"
    if fmt == "markdown":
        return render_markdown(selection)
    return render_text(selection)


def record_selection(selection: dict[str, Any], evidence_dir: Path | None, record_dir: Path | None) -> dict[str, str]:
    target = record_dir
    if target is None:
        if evidence_dir is None:
            raise ValueError("--record requires --evidence-dir or --record-dir")
        target = evidence_dir / ".kubeactuary"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / RECORD_JSON
    md_path = target / RECORD_MD
    json_path.write_text(render_payload(selection, "json"))
    md_path.write_text(render_payload(selection, "markdown"))
    return {"json": json_path.as_posix(), "markdown": md_path.as_posix()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select the next KubeActuary unblock action.")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    parser.add_argument("--record", action="store_true", help="write next-unblock-action JSON and Markdown metadata")
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
        selection = build_selection(
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
        record_paths = record_selection(selection, evidence_dir, record_dir) if args.record else None
    except ValueError as exc:
        print("next-unblock-action: failed", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rendered = render_payload(selection, args.format)
    if args.output == "-":
        print(rendered, end="")
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        print(f"next-unblock-action: wrote {args.output}")
    if record_paths and args.output != "-":
        print(f"next-unblock-action: recorded {record_paths['json']}")
        print(f"next-unblock-action: recorded {record_paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
