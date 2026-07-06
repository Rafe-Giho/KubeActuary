#!/usr/bin/env python3
"""Generate an actionable queue for remaining live validation evidence."""

from __future__ import annotations

import argparse
import json
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


def missing_tools_for_gate(gate: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    readiness_by_gate = {
        item.get("gate"): item
        for item in readiness.get("gateToolReadiness", [])
        if isinstance(item, dict)
    }
    readiness_gate_names = KIND_READINESS_GATES.get(str(gate.get("kind")), ())
    return sorted(
        {
            tool
            for name in readiness_gate_names
            for tool in readiness_by_gate.get(name, {}).get("missingTools", [])
        }
    )


def build_item(gate: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    missing_tools = missing_tools_for_gate(gate, readiness)
    commands = list(gate.get("recommendedCommands") or [])
    status = "tool-ready" if not missing_tools else "missing-tools"
    return {
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
            else "install missing tools or run on a host that has them"
        ),
    }


def build_queue() -> dict[str, Any]:
    plan = build_plan()
    readiness = build_readiness_report()
    items = [build_item(gate, readiness) for gate in plan.get("gates", [])]
    tool_ready = sum(1 for item in items if item["status"] == "tool-ready")
    missing_tools = sorted({tool for item in items for tool in item["missingTools"]})
    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": str(TASKBOARD.relative_to(ROOT)),
        "mode": "inventory-only",
        "clusterWrites": "disabled",
        "summary": {
            "total": len(items),
            "toolReady": tool_ready,
            "blockedByTools": len(items) - tool_ready,
            "missingTools": missing_tools,
        },
        "items": items,
        "closureCommands": list(plan.get("closureCommands", [])),
    }


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
        f"- missing-tools: {', '.join(summary['missingTools']) if summary['missingTools'] else 'none'}",
        "",
    ]
    for heading, status in (("Tool-Ready", "tool-ready"), ("Missing Tools", "missing-tools")):
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
            for command in item["commands"]:
                lines.append(f"  Command: `{command}`")
            lines.append(f"  Next: {item['nextStep']}")
        lines.append("")
    lines.extend(["## Closure", ""])
    for command in queue["closureCommands"]:
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary live validation queue.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    queue = build_queue()
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
