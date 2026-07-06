#!/usr/bin/env python3
"""Generate a structured plan for remaining external verification gates."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
SCHEMA_VERSION = "kube-actuary.external-gate-plan.v1"
ALLOWED_STATUSES = {"DONE", "VERIFY", "DOING", "TODO", "BLOCKED"}
PROVIDER_COMMANDS = {
    "lightweight": [
        "python3 -B scripts/run_lightweight_cluster_smoke.py --provider kind --run --output <path>",
        "python3 -B scripts/run_lightweight_cluster_smoke.py --provider minikube --run --output <path>",
        "python3 -B scripts/run_lightweight_cluster_smoke.py --provider microk8s --run --output <path>",
        "python3 -B scripts/run_lightweight_cluster_smoke.py --provider k3s --run --output <path>",
    ],
    "managed": [
        "python3 -B scripts/run_managed_kubernetes_smoke.py --provider eks --run --output <path>",
        "python3 -B scripts/run_managed_kubernetes_smoke.py --provider gke --run --output <path>",
        "python3 -B scripts/run_managed_kubernetes_smoke.py --provider aks --run --output <path>",
    ],
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "gate"


def taskboard_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line.lstrip("#").strip()
            continue
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 3 and cells[1] in ALLOWED_STATUSES:
            rows.append({"section": section, "item": cells[0], "status": cells[1], "evidence": cells[2]})
        elif len(cells) == 4 and cells[2] in ALLOWED_STATUSES:
            rows.append(
                {
                    "section": section,
                    "version": cells[0],
                    "item": cells[1],
                    "status": cells[2],
                    "evidence": cells[3],
                }
            )
    return rows


def gate_kind(item: str, evidence: str) -> str:
    text = f"{item} {evidence}".lower()
    if "admission" in text or "webhook" in text:
        return "admission"
    if "resource budget" in text:
        return "controller-resource-budget"
    if "managed" in text or "eks" in text or "gke" in text or "aks" in text:
        return "managed-kubernetes"
    if "packaging" in text:
        return "packaging"
    if "lightweight" in text or "kind" in text or "minikube" in text or "microk8s" in text or "k3s" in text:
        return "lightweight-cluster"
    if "helm" in text:
        return "helm"
    if "krew" in text:
        return "krew"
    if "crd" in text or "explain" in text:
        return "crd"
    if "controller" in text:
        return "controller"
    return "external"


def recommended_commands(kind: str) -> list[str]:
    if kind == "lightweight-cluster":
        return PROVIDER_COMMANDS["lightweight"]
    if kind == "managed-kubernetes":
        return PROVIDER_COMMANDS["managed"]
    if kind == "helm":
        return ["python3 -B scripts/run_helm_smoke.py --run --output <path>"]
    if kind == "krew":
        return ["python3 -B scripts/run_krew_smoke.py --run --output <path>"]
    if kind == "packaging":
        return [
            "python3 -B scripts/run_helm_smoke.py --run --output <path>",
            "python3 -B scripts/run_krew_smoke.py --run --output <path>",
        ]
    if kind == "admission":
        return ["python3 -B scripts/run_admission_kind_smoke.py --run --output <path>"]
    if kind == "controller-resource-budget":
        return ["python3 -B scripts/measure_controller_resources.py --sample <kubectl-top-output.txt>"]
    if kind == "crd":
        return [
            "kubectl apply --dry-run=server -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
            "kubectl explain operationcapsules --api-version=ops.kubeactuary.dev/v1alpha1",
        ]
    return []


def external_gate(row: dict[str, str], index: int) -> dict[str, Any]:
    kind = gate_kind(row["item"], row["evidence"])
    return {
        "id": f"{index:02d}-{slugify(row['item'])}",
        "section": row["section"],
        "version": row.get("version"),
        "item": row["item"],
        "kind": kind,
        "status": row["status"],
        "requiredEvidence": row["evidence"],
        "recommendedCommands": recommended_commands(kind),
    }


def build_plan(taskboard: Path = TASKBOARD) -> dict[str, Any]:
    text = taskboard.read_text()
    rows = taskboard_rows(text)
    statuses = Counter(row["status"] for row in rows)
    verify_rows = [row for row in rows if row["status"] == "VERIFY"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "source": str(taskboard.relative_to(ROOT)),
        "summary": {
            "rows": len(rows),
            "done": statuses["DONE"],
            "verify": statuses["VERIFY"],
            "doing": statuses["DOING"],
            "todo": statuses["TODO"],
            "blocked": statuses["BLOCKED"],
        },
        "gates": [external_gate(row, index + 1) for index, row in enumerate(verify_rows)],
        "closureCommands": [
            "python3 -B scripts/validate_live_evidence.py <evidence.json> [...]",
            "python3 -B scripts/build_live_evidence_manifest.py <evidence.json> [...] --output <manifest.json>",
            "python3 -B scripts/check_live_evidence_coverage.py <manifest.json>",
        ],
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# External Verification Gate Plan",
        "",
        f"Schema: `{plan['schemaVersion']}`",
        f"Source: `{plan['source']}`",
        "",
        "## Summary",
        "",
        f"- verify: {plan['summary']['verify']}",
        f"- doing: {plan['summary']['doing']}",
        f"- todo: {plan['summary']['todo']}",
        "",
        "## Gates",
        "",
    ]
    for gate in plan["gates"]:
        lines.append(f"- `{gate['id']}` {gate['item']} ({gate['kind']})")
        lines.append(f"  Required evidence: {gate['requiredEvidence']}")
        if gate["recommendedCommands"]:
            lines.append(f"  First command: `{gate['recommendedCommands'][0]}`")
    lines.extend(["", "## Closure", ""])
    for command in plan["closureCommands"]:
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary external verification gate plan.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    plan = build_plan()
    if args.format == "json":
        rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_markdown(plan)

    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"external-gate-plan: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
