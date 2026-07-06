#!/usr/bin/env python3
"""Generate an actionable queue for remaining live validation evidence."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_external_gate_plan import TASKBOARD, build_plan  # noqa: E402
from scripts.verify_live_validation_readiness import build_report as build_readiness_report  # noqa: E402


SCHEMA_VERSION = "kube-actuary.live-validation-queue.v1"
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


def readiness_lookup(readiness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item.get("gate"): item
        for item in readiness.get("gateToolReadiness", [])
        if isinstance(item, dict)
    }


def missing_tools_for_gate(gate: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    readiness_by_gate = readiness_lookup(readiness)
    readiness_gate_names = KIND_READINESS_GATES.get(str(gate.get("kind")), ())
    return sorted(
        {
            tool
            for name in readiness_gate_names
            for tool in readiness_by_gate.get(name, {}).get("missingTools", [])
        }
    )


def environment_status_for_gate(gate: dict[str, Any], readiness: dict[str, Any]) -> str | None:
    if not readiness.get("environmentProbe"):
        return None
    readiness_by_gate = readiness_lookup(readiness)
    readiness_gate_names = KIND_READINESS_GATES.get(str(gate.get("kind")), ())
    statuses = [
        readiness_by_gate.get(name, {}).get("environmentStatus")
        for name in readiness_gate_names
        if readiness_by_gate.get(name, {}).get("environmentStatus")
    ]
    if "cluster-unavailable" in statuses:
        return "cluster-unavailable"
    if "cluster-available" in statuses:
        return "cluster-available"
    if statuses:
        return "not-required"
    return None


def evidence_path(evidence_dir: Path, *parts: str) -> str:
    return evidence_dir.joinpath(*parts).as_posix()


def provider_from_command(command: str) -> str | None:
    tokens = shlex.split(command)
    if "--provider" not in tokens:
        return None
    index = tokens.index("--provider")
    if index + 1 >= len(tokens):
        return None
    return tokens[index + 1]


def report_output_path(item: dict[str, Any], command: str, evidence_dir: Path, index: int) -> str:
    item_id = str(item["id"])
    provider = provider_from_command(command)
    if "run_lightweight_cluster_smoke.py" in command and provider:
        name = f"{item_id}-lightweight-{provider}.json"
    elif "run_managed_kubernetes_smoke.py" in command and provider:
        name = f"{item_id}-managed-{provider}.json"
    elif "run_helm_smoke.py" in command:
        name = f"{item_id}-helm-smoke.json"
    elif "run_krew_smoke.py" in command:
        name = f"{item_id}-krew-smoke.json"
    elif "run_admission_kind_smoke.py" in command:
        name = f"{item_id}-admission-kind-smoke.json"
    else:
        name = f"{item_id}-report-{index}.json"
    return evidence_path(evidence_dir, "reports", name)


def materialize_command(item: dict[str, Any], command: str, evidence_dir: Path, index: int) -> str:
    item_id = str(item["id"])
    replacements = {
        "<kubectl-top-output.txt>": evidence_path(evidence_dir, "raw", f"{item_id}-kubectl-top.txt"),
        "<controller-loop-output.json>": evidence_path(evidence_dir, "raw", f"{item_id}-controller-loop-output.json"),
        "<kubectl-explain-output.txt>": evidence_path(evidence_dir, "raw", f"{item_id}-kubectl-explain-output.txt"),
        "<external-evidence.json>": evidence_path(evidence_dir, "supplemental", f"{item_id}-external-{index}.json"),
    }
    rendered = command.replace("<path>", report_output_path(item, command, evidence_dir, index))
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def build_item(gate: dict[str, Any], readiness: dict[str, Any], evidence_dir: Path | None = None) -> dict[str, Any]:
    missing_tools = missing_tools_for_gate(gate, readiness)
    environment_status = environment_status_for_gate(gate, readiness)
    commands = list(gate.get("recommendedCommands") or [])
    status = "tool-ready" if not missing_tools else "missing-tools"
    if status == "tool-ready" and environment_status == "cluster-unavailable":
        status = "blocked-by-environment"
    item = {
        "id": gate.get("id"),
        "version": gate.get("version") or gate.get("section"),
        "item": gate.get("item"),
        "kind": gate.get("kind"),
        "status": status,
        "missingTools": missing_tools,
        "commands": commands,
        "nextStep": (
            "capture evidence with the listed commands"
            if status == "tool-ready"
            else "start or select a disposable cluster, then rerun the probe"
            if status == "blocked-by-environment"
            else "install missing tools or run on a host that has them"
        ),
    }
    if environment_status is not None:
        item["environmentStatus"] = environment_status
    if evidence_dir is not None:
        item["evidenceDir"] = evidence_dir.as_posix()
        item["resolvedCommands"] = [
            materialize_command(item, command, evidence_dir, index + 1)
            for index, command in enumerate(commands)
        ]
    return item


def resolved_closure_commands(evidence_dir: Path) -> list[str]:
    manifest = evidence_path(evidence_dir, ".kubeactuary", "live-evidence-manifest.json")
    return [
        f"python3 -B scripts/validate_live_evidence.py {evidence_path(evidence_dir, 'reports', '*.json')}",
        (
            "python3 -B scripts/build_live_evidence_manifest.py "
            f"{evidence_path(evidence_dir, 'reports', '*.json')} --output {manifest}"
        ),
        f"python3 -B scripts/check_live_evidence_coverage.py {manifest}",
        f"python3 -B scripts/build_release_evidence_directory.py {evidence_dir.as_posix()}",
    ]


def build_queue(
    evidence_dir: Path | None = None,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
) -> dict[str, Any]:
    plan = build_plan()
    readiness = build_readiness_report(probe_environment=probe_environment, kubectl=kubectl)
    items = [build_item(gate, readiness, evidence_dir) for gate in plan.get("gates", [])]
    tool_ready = sum(1 for item in items if item["status"] == "tool-ready")
    blocked_by_environment = sum(1 for item in items if item["status"] == "blocked-by-environment")
    blocked_by_tools = sum(1 for item in items if item["status"] == "missing-tools")
    missing_tools = sorted({tool for item in items for tool in item["missingTools"]})
    queue = {
        "schemaVersion": SCHEMA_VERSION,
        "source": str(TASKBOARD.relative_to(ROOT)),
        "mode": "inventory-plus-environment-probe" if probe_environment else "inventory-only",
        "clusterWrites": "disabled",
        "summary": {
            "total": len(items),
            "toolReady": tool_ready,
            "blockedByTools": blocked_by_tools,
            "blockedByEnvironment": blocked_by_environment,
            "missingTools": missing_tools,
        },
        "items": items,
        "closureCommands": list(plan.get("closureCommands", [])),
    }
    if readiness.get("environmentProbe"):
        queue["environmentProbe"] = readiness["environmentProbe"]
    if evidence_dir is not None:
        queue["evidenceDir"] = evidence_dir.as_posix()
        queue["resolvedClosureCommands"] = resolved_closure_commands(evidence_dir)
    return queue


def render_markdown(queue: dict[str, Any]) -> str:
    summary = queue["summary"]
    lines = [
        "# Live Validation Queue",
        "",
        f"Schema: `{queue['schemaVersion']}`",
        f"Source: `{queue['source']}`",
        f"Mode: `{queue['mode']}`",
        f"Cluster writes: `{queue['clusterWrites']}`",
        "",
        "## Summary",
        "",
        f"- total: {summary['total']}",
        f"- tool-ready: {summary['toolReady']}",
        f"- blocked-by-tools: {summary['blockedByTools']}",
        f"- blocked-by-environment: {summary.get('blockedByEnvironment', 0)}",
        f"- missing-tools: {', '.join(summary['missingTools']) if summary['missingTools'] else 'none'}",
        "",
    ]
    for heading, status in (
        ("Tool-Ready", "tool-ready"),
        ("Blocked By Environment", "blocked-by-environment"),
        ("Missing Tools", "missing-tools"),
    ):
        lines.extend([f"## {heading}", ""])
        matching = [item for item in queue["items"] if item["status"] == status]
        if not matching:
            lines.append("- none")
            lines.append("")
            continue
        for item in matching:
            lines.append(f"- `{item['id']}` {item['item']} ({item['version']}, {item['kind']})")
            if item["missingTools"]:
                lines.append(f"  Missing tools: `{', '.join(item['missingTools'])}`")
            if item.get("environmentStatus"):
                lines.append(f"  Environment: `{item['environmentStatus']}`")
            for command in item["commands"]:
                lines.append(f"  Command: `{command}`")
            for command in item.get("resolvedCommands", []):
                lines.append(f"  Resolved: `{command}`")
            lines.append(f"  Next: {item['nextStep']}")
        lines.append("")
    lines.extend(["## Closure", ""])
    for command in queue["closureCommands"]:
        lines.append(f"- `{command}`")
    if queue.get("resolvedClosureCommands"):
        lines.extend(["", "## Resolved Closure", ""])
        for command in queue["resolvedClosureCommands"]:
            lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary live validation queue.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--evidence-dir", help="optional evidence directory for deterministic command paths")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else None
    queue = build_queue(evidence_dir, probe_environment=args.probe_environment, kubectl=args.kubectl)
    if args.format == "json":
        rendered = json.dumps(queue, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_markdown(queue)

    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"live-validation-queue: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
