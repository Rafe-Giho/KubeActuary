#!/usr/bin/env python3
"""Verify local GA release-gate readiness without external probes."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_release import COMMON_CHECKS
from scripts.verify_release_taskboard import taskboard_rows


TASKBOARD = ROOT / "docs" / "release-taskboard.md"

REQUIRED_GA_GATES = (
    "CLI, CRD, controller, packaging, MCP-safe tools, and docs are all verified.",
    "Default behavior still does not execute proposed Kubernetes writes.",
    "Controller watches only KubeActuary CRDs.",
    "Admission remains optional.",
    "Support matrix is documented for upstream-supported Kubernetes minors,",
    "License, NOTICE, SECURITY, CONTRIBUTING, and release provenance are complete.",
)

REQUIRED_RELEASE_CHECKS = (
    "unit tests",
    "release taskboard",
    "release progress",
    "crd compatibility smoke",
    "controller contract",
    "controller runtime",
    "helm chart",
    "krew manifest",
    "supply chain",
    "security docs",
    "docs freeze",
    "project governance",
    "mcp contract",
    "mcp docs",
    "execute disabled",
    "admission webhook",
)

REQUIRED_FILES = {
    "README.md": (
        "no direct cluster write execution;",
        "controller should watch only KubeActuary resources;",
        "optional admission webhook",
    ),
    "README.ko.md": (
        "cluster-wide scan",
        "OperationCapsule",
        "optional admission webhook",
    ),
    "LICENSE": ("MIT License",),
    "NOTICE": ("KubeActuary", "MIT License"),
    "SECURITY.md": ("Reporting a Vulnerability",),
    "CONTRIBUTING.md": ("Safety Boundary",),
    "docs/controller.md": (
        "The controller remains optional.",
        "It must not watch Pods, Deployments, Nodes, Events, Namespaces, or arbitrary",
        "execute proposed Kubernetes writes",
    ),
    "docs/admission.md": (
        "KubeActuary admission is optional.",
        "failurePolicy: Ignore",
        "no direct Kubernetes write execution by KubeActuary",
    ),
    "docs/mcp.md": (
        "does not expose raw Kubernetes write execution",
        "execute_approved_capsule` remains disabled",
    ),
    "docs/kubernetes-compatibility.md": (
        "Upstream Kubernetes",
        "Managed Kubernetes",
        "Local Validation Scope",
    ),
    "docs/supply-chain.md": ("SBOM", "provenance"),
}


def main() -> int:
    errors: list[str] = []
    taskboard = TASKBOARD.read_text()
    rows = taskboard_rows(taskboard)
    statuses = Counter(row["status"] for row in rows)

    if "## v1.0.0: GA" not in taskboard:
        errors.append("taskboard missing v1.0.0 GA section")
    for gate in REQUIRED_GA_GATES:
        if gate not in taskboard:
            errors.append(f"taskboard missing GA gate: {gate}")

    if statuses["VERIFY"] != 0:
        errors.append(f"GA readiness requires zero VERIFY rows, got {statuses['VERIFY']}")
    if statuses["DOING"] != 0 or statuses["TODO"] != 0:
        errors.append("GA readiness requires zero DOING/TODO rows")
    if statuses["BLOCKED"] != 16:
        errors.append(f"GA readiness must preserve 16 accepted live blockers, got {statuses['BLOCKED']}")

    check_names = {check.name for check in COMMON_CHECKS}
    for check_name in REQUIRED_RELEASE_CHECKS:
        if check_name not in check_names:
            errors.append(f"release suite missing GA check: {check_name}")

    for relative, snippets in REQUIRED_FILES.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing GA support file: {relative}")
            continue
        text = path.read_text()
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{relative} missing: {snippet}")

    if errors:
        print("ga-readiness: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("ga-readiness: passed")
    print(f"done: {statuses['DONE']}")
    print(f"blocked: {statuses['BLOCKED']}")
    print("verify: 0")
    print(f"release-checks: {len(COMMON_CHECKS)}")
    print(f"ga-gates: {len(REQUIRED_GA_GATES)}")
    print("cluster-writes: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
