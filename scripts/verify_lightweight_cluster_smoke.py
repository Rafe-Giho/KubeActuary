#!/usr/bin/env python3
"""Verify the lightweight cluster smoke harness without requiring clusters."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "run_lightweight_cluster_smoke.py"
DOC = ROOT / "docs" / "lightweight-cluster-smoke.md"
PROVIDERS = ("kind", "minikube", "microk8s", "k3s")


def run_plan(provider: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SMOKE), "--provider", provider],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    for provider in PROVIDERS:
        result = run_plan(provider)
        output = result.stdout
        if result.returncode != 0:
            errors.append(f"{provider}: plan failed: {result.stderr.strip()}")
            continue
        for required in (
            "lightweight-cluster-smoke: plan",
            f"provider: {provider}",
            "kubectl apply --dry-run=server -f deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
            "kubectl apply --dry-run=server -f deploy/controller/namespace-scoped-rbac.yaml",
            "kubectl apply --dry-run=server -f deploy/controller/cluster-scoped-rbac.yaml",
            "kubectl auth can-i get operationcapsules.ops.kubeactuary.dev --all-namespaces",
            "kubectl top pod -n kubeactuary-system",
        ):
            if required not in output:
                errors.append(f"{provider}: plan missing {required}")
        for forbidden in ("kubectl apply -f", "kubectl delete", "kubectl create deployment", " pods --all-namespaces"):
            if forbidden in output:
                errors.append(f"{provider}: plan includes forbidden operation {forbidden}")

    doc = DOC.read_text()
    for required in (
        "kind",
        "minikube",
        "MicroK8s",
        "k3s",
        "server-side dry-run",
        "scripts/run_lightweight_cluster_smoke.py",
    ):
        if required not in doc:
            errors.append(f"smoke doc missing: {required}")

    if errors:
        print("lightweight-cluster-smoke: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("lightweight-cluster-smoke: passed")
    print("providers: kind, minikube, microk8s, k3s")
    print("mode: offline-plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
