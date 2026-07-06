#!/usr/bin/env python3
"""Verify optional controller runtime contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "bin" / "kube-actuary-controller"
DOC = ROOT / "docs" / "controller.md"
WATCH_RESOURCE = "operationcapsules.ops.kubeactuary.dev"


def run_controller(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTROLLER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_json_command(errors: list[str], *args: str) -> dict:
    result = run_controller(*args)
    if result.returncode != 0:
        errors.append(f"{args[0]} failed: {result.stderr.strip()}")
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"{args[0]} did not emit JSON: {exc}")
        return {}


def main() -> int:
    errors: list[str] = []

    health = load_json_command(errors, "health", "--started-at", "100", "--now", "125")
    if health.get("status") != "ok":
        errors.append("health status must be ok")
    if health.get("watchResource") != WATCH_RESOURCE:
        errors.append("health payload missing OperationCapsule watch resource")
    if health.get("uptimeSeconds") != 25:
        errors.append("health uptime calculation is not deterministic")

    ready = load_json_command(errors, "ready", "--rbac-mode", "cluster")
    checks = ready.get("checks", {})
    if ready.get("ready") is not True:
        errors.append("ready payload must be ready")
    if checks.get("watchResource") != WATCH_RESOURCE:
        errors.append("ready payload missing OperationCapsule watch resource")
    if checks.get("statusPatchOnly") is not True:
        errors.append("ready payload must assert statusPatchOnly")
    if checks.get("rbacMode") != "cluster":
        errors.append("ready payload did not preserve RBAC mode")

    metrics = run_controller(
        "metrics",
        "--reconcile-total",
        "3",
        "--reconcile-errors-total",
        "1",
        "--gate-open-total",
        "2",
    )
    if metrics.returncode != 0:
        errors.append(f"metrics failed: {metrics.stderr.strip()}")
    if "# TYPE kubeactuary_controller_reconcile_total counter" not in metrics.stdout:
        errors.append("metrics missing reconcile counter type")
    if "kubeactuary_controller_reconcile_total 3" not in metrics.stdout:
        errors.append("metrics missing reconcile total value")
    if WATCH_RESOURCE not in metrics.stdout:
        errors.append("metrics missing OperationCapsule watch resource label")

    election = load_json_command(errors, "leader-election", "--identity", "verifier")
    if election.get("resource") != "leases.coordination.k8s.io":
        errors.append("leader election must use coordination.k8s.io Lease")
    if election.get("namespace") != "kubeactuary-system":
        errors.append("leader election namespace changed unexpectedly")
    if election.get("leaseName") != "kubeactuary-controller":
        errors.append("leader election lease name changed unexpectedly")
    if election.get("identity") != "verifier":
        errors.append("leader election identity override failed")

    doc = DOC.read_text()
    for required in ("/healthz", "/readyz", "/metrics", "Lease", "leases.coordination.k8s.io"):
        if required not in doc:
            errors.append(f"controller doc missing runtime contract: {required}")

    if errors:
        print("controller-runtime: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-runtime: passed")
    print("health: ok")
    print("ready: ok")
    print("metrics: prometheus-text")
    print("leader-election: leases.coordination.k8s.io")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
