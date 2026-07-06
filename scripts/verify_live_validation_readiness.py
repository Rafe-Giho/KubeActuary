#!/usr/bin/env python3
"""Inventory readiness for live validation gates without running them."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "live-validation.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"

TOOLS = (
    "kubectl",
    "kind",
    "minikube",
    "microk8s",
    "k3s",
    "helm",
    "kubectl-krew",
    "aws",
    "gcloud",
    "az",
)

GATES = (
    "CRD live apply/explain smoke",
    "controller resource budget measurement",
    "lightweight cluster smoke matrix",
    "Helm template and install smoke",
    "Krew install smoke",
    "managed Kubernetes EKS/GKE/AKS smoke",
    "admission webhook live kind smoke",
)

DOC_SNIPPETS = (
    "inventory-only",
    "does not contact a cluster",
    "does not contact cloud APIs",
    "kind, minikube, MicroK8s, and k3s",
    "EKS, GKE, and AKS",
    "provider run evidence",
    "cluster-writes: disabled",
)

TASKBOARD_SNIPPETS = (
    "Live validation readiness",
    "verify_live_validation_readiness.py",
    "Managed Kubernetes smoke: EKS, GKE, AKS",
)


def tool_status() -> dict[str, dict[str, str | None]]:
    status: dict[str, dict[str, str | None]] = {}
    for tool in TOOLS:
        path = shutil.which(tool)
        status[tool] = {
            "status": "available" if path else "missing",
            "path": path,
        }
    return status


def build_report() -> dict[str, Any]:
    tools = tool_status()
    available = sum(1 for item in tools.values() if item["status"] == "available")
    return {
        "schemaVersion": "kube-actuary.live-validation-readiness.v1",
        "mode": "inventory-only",
        "clusterWrites": "disabled",
        "liveGates": list(GATES),
        "tools": tools,
        "summary": {
            "toolsAvailable": available,
            "toolsTotal": len(TOOLS),
            "liveGates": len(GATES),
        },
    }


def verify_docs(errors: list[str]) -> None:
    if not DOC.is_file():
        errors.append(f"missing doc: {DOC.relative_to(ROOT)}")
        return
    text = DOC.read_text()
    for snippet in DOC_SNIPPETS:
        if snippet not in text:
            errors.append(f"live validation doc missing: {snippet}")


def verify_taskboard(errors: list[str]) -> None:
    if not TASKBOARD.is_file():
        errors.append(f"missing taskboard: {TASKBOARD.relative_to(ROOT)}")
        return
    text = TASKBOARD.read_text()
    for snippet in TASKBOARD_SNIPPETS:
        if snippet not in text:
            errors.append(f"taskboard missing: {snippet}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = False
    if argv == ["--json"]:
        as_json = True
    elif argv:
        print("usage: verify_live_validation_readiness.py [--json]", file=sys.stderr)
        return 2

    errors: list[str] = []
    verify_docs(errors)
    verify_taskboard(errors)
    report = build_report()

    if errors:
        print("live-validation-readiness: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    summary = report["summary"]
    print("live-validation-readiness: passed")
    print("mode: inventory-only")
    print(f"live-gates: {summary['liveGates']}")
    print(f"tools: {summary['toolsAvailable']}/{summary['toolsTotal']} available")
    print("cluster-writes: disabled")
    print(f"evidence-ledger: {DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
