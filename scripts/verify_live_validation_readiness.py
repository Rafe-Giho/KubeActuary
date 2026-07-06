#!/usr/bin/env python3
"""Inventory readiness for live validation gates without running them."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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
GATE_TOOL_REQUIREMENTS = (
    ("CRD live apply/explain smoke", ("kubectl",)),
    ("controller resource budget measurement", ("kubectl",)),
    ("lightweight cluster smoke matrix", ("kubectl", "kind", "minikube", "microk8s", "k3s")),
    ("Helm template and install smoke", ("kubectl", "helm")),
    ("Krew install smoke", ("kubectl-krew",)),
    ("managed Kubernetes EKS/GKE/AKS smoke", ("kubectl", "aws", "gcloud", "az")),
    ("admission webhook live kind smoke", ("kubectl", "kind")),
)
CLUSTER_REQUIRED_GATES = {
    "CRD live apply/explain smoke",
    "controller resource budget measurement",
    "lightweight cluster smoke matrix",
    "Helm template and install smoke",
    "managed Kubernetes EKS/GKE/AKS smoke",
    "admission webhook live kind smoke",
}

DOC_SNIPPETS = (
    "inventory-only",
    "does not contact a cluster",
    "does not contact cloud APIs",
    "kind, minikube, MicroK8s, and k3s",
    "EKS, GKE, and AKS",
    "provider run evidence",
    "cluster-writes: disabled",
    "tool-ready-gates",
    "--probe-environment",
    "environment-probe",
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


def gate_tool_readiness(tools: dict[str, dict[str, str | None]]) -> list[dict[str, Any]]:
    readiness: list[dict[str, Any]] = []
    for gate, required in GATE_TOOL_REQUIREMENTS:
        missing = [tool for tool in required if tools[tool]["status"] != "available"]
        readiness.append(
            {
                "gate": gate,
                "requiredTools": list(required),
                "missingTools": missing,
                "status": "tool-ready" if not missing else "missing-tools",
            }
        )
    return readiness


def run_probe(name: str, command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "name": name,
            "command": command,
            "ok": False,
            "exitCode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "ok": False,
            "exitCode": None,
            "stdout": exc.stdout or "",
            "stderr": "timed out",
        }
    return {
        "name": name,
        "command": command,
        "ok": result.returncode == 0,
        "exitCode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def environment_probe(kubectl: str) -> dict[str, Any]:
    client = run_probe("kubectl-client", [kubectl, "version", "--client=true"])
    cluster = run_probe("cluster-info", [kubectl, "cluster-info", "--request-timeout=5s"])
    if not client["ok"]:
        cluster_access = "kubectl-unavailable"
    elif cluster["ok"]:
        cluster_access = "available"
    else:
        cluster_access = "unavailable"
    return {
        "enabled": True,
        "clusterWrites": "disabled",
        "kubectl": kubectl,
        "clusterAccess": cluster_access,
        "checks": [client, cluster],
    }


def add_environment_status(gates: list[dict[str, Any]], probe: dict[str, Any]) -> None:
    cluster_available = probe.get("clusterAccess") == "available"
    for gate in gates:
        if gate.get("gate") not in CLUSTER_REQUIRED_GATES:
            gate["environmentStatus"] = "not-required"
        elif cluster_available:
            gate["environmentStatus"] = "cluster-available"
        else:
            gate["environmentStatus"] = "cluster-unavailable"


def build_report(probe_environment: bool = False, kubectl: str = "kubectl") -> dict[str, Any]:
    tools = tool_status()
    gates = gate_tool_readiness(tools)
    probe: dict[str, Any] | None = None
    if probe_environment:
        probe = environment_probe(kubectl)
        add_environment_status(gates, probe)
    available = sum(1 for item in tools.values() if item["status"] == "available")
    ready_gates = sum(1 for gate in gates if gate["status"] == "tool-ready")
    summary = {
        "toolsAvailable": available,
        "toolsTotal": len(TOOLS),
        "liveGates": len(GATES),
        "toolReadyGates": ready_gates,
    }
    if probe is not None:
        summary["blockedByEnvironment"] = sum(
            1
            for gate in gates
            if gate["status"] == "tool-ready" and gate.get("environmentStatus") == "cluster-unavailable"
        )
    report = {
        "schemaVersion": "kube-actuary.live-validation-readiness.v1",
        "mode": "inventory-plus-environment-probe" if probe is not None else "inventory-only",
        "clusterWrites": "disabled",
        "liveGates": list(GATES),
        "gateToolReadiness": gates,
        "tools": tools,
        "summary": summary,
    }
    if probe is not None:
        report["environmentProbe"] = probe
    return report


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
    parser = argparse.ArgumentParser(description="Inventory readiness for KubeActuary live validation gates.")
    parser.add_argument("--json", action="store_true", help="emit the readiness report as JSON")
    parser.add_argument(
        "--probe-environment",
        action="store_true",
        help="run read-only kubectl checks to classify current cluster availability",
    )
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    args = parser.parse_args(argv)

    errors: list[str] = []
    verify_docs(errors)
    verify_taskboard(errors)
    report = build_report(probe_environment=args.probe_environment, kubectl=args.kubectl)

    if errors:
        print("live-validation-readiness: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    summary = report["summary"]
    print("live-validation-readiness: passed")
    print(f"mode: {report['mode']}")
    print(f"live-gates: {summary['liveGates']}")
    print(f"tool-ready-gates: {summary['toolReadyGates']}/{summary['liveGates']}")
    print(f"tools: {summary['toolsAvailable']}/{summary['toolsTotal']} available")
    if args.probe_environment:
        print(f"environment-probe: {report['environmentProbe']['clusterAccess']}")
        print(f"blocked-by-environment: {summary['blockedByEnvironment']}")
    print("cluster-writes: disabled")
    print(f"evidence-ledger: {DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
