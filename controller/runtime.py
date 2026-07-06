"""Runtime contracts for the optional controller.

The functions in this module are deterministic and dependency-free so they can
be tested before a live Kubernetes controller process exists.
"""

from __future__ import annotations

import socket
import time
from typing import Any

from controller.reconcile import WATCH_RESOURCE


COMPONENT = "kube-actuary-controller"
DEFAULT_NAMESPACE = "kubeactuary-system"
DEFAULT_LEASE_NAME = "kubeactuary-controller"
LEASE_RESOURCE = "leases.coordination.k8s.io"
RESOURCE_BUDGET = {
    "idleCpuMillicoresLessThan": 50,
    "idleMemoryMiLessThan": 64,
    "requests": {"cpu": "10m", "memory": "32Mi"},
    "limits": {"cpu": "50m", "memory": "64Mi"},
}
CONTROLLER_SELECTOR = "app.kubernetes.io/name=kubeactuary,app.kubernetes.io/component=controller"


def health_payload(started_at: int | None = None, now: int | None = None) -> dict[str, Any]:
    current = int(now if now is not None else time.time())
    started = int(started_at if started_at is not None else current)
    return {
        "status": "ok",
        "component": COMPONENT,
        "watchResource": WATCH_RESOURCE,
        "uptimeSeconds": max(0, current - started),
        "checks": {
            "runtime": "ok",
            "watchBoundary": "ok",
        },
    }


def readiness_payload(rbac_mode: str = "namespace", leader_election: bool = True) -> dict[str, Any]:
    if rbac_mode not in ("namespace", "cluster"):
        raise ValueError(f"invalid RBAC mode: {rbac_mode}")
    return {
        "ready": True,
        "component": COMPONENT,
        "checks": {
            "reconcileModel": "ready",
            "watchResource": WATCH_RESOURCE,
            "statusPatchOnly": True,
            "rbacMode": rbac_mode,
            "leaderElectionConfigured": leader_election,
        },
    }


def metrics_text(
    reconcile_total: int = 0,
    reconcile_errors_total: int = 0,
    gate_open_total: int = 0,
) -> str:
    lines = [
        "# HELP kubeactuary_controller_info Controller build and watch metadata.",
        "# TYPE kubeactuary_controller_info gauge",
        (
            'kubeactuary_controller_info{component="'
            f'{COMPONENT}",watch_resource="{WATCH_RESOURCE}"'
            "} 1"
        ),
        "# HELP kubeactuary_controller_reconcile_total Reconcile attempts.",
        "# TYPE kubeactuary_controller_reconcile_total counter",
        f"kubeactuary_controller_reconcile_total {reconcile_total}",
        "# HELP kubeactuary_controller_reconcile_errors_total Failed reconcile attempts.",
        "# TYPE kubeactuary_controller_reconcile_errors_total counter",
        f"kubeactuary_controller_reconcile_errors_total {reconcile_errors_total}",
        "# HELP kubeactuary_controller_gate_open_total Capsules reconciled with open gates.",
        "# TYPE kubeactuary_controller_gate_open_total counter",
        f"kubeactuary_controller_gate_open_total {gate_open_total}",
        "# HELP kubeactuary_controller_idle_cpu_budget_millicores Idle CPU budget target.",
        "# TYPE kubeactuary_controller_idle_cpu_budget_millicores gauge",
        (
            "kubeactuary_controller_idle_cpu_budget_millicores "
            f"{RESOURCE_BUDGET['idleCpuMillicoresLessThan']}"
        ),
        "# HELP kubeactuary_controller_idle_memory_budget_mebibytes Idle memory budget target.",
        "# TYPE kubeactuary_controller_idle_memory_budget_mebibytes gauge",
        (
            "kubeactuary_controller_idle_memory_budget_mebibytes "
            f"{RESOURCE_BUDGET['idleMemoryMiLessThan']}"
        ),
    ]
    return "\n".join(lines) + "\n"


def leader_election_config(
    namespace: str = DEFAULT_NAMESPACE,
    lease_name: str = DEFAULT_LEASE_NAME,
    identity: str | None = None,
) -> dict[str, Any]:
    return {
        "enabled": True,
        "resource": LEASE_RESOURCE,
        "namespace": namespace,
        "leaseName": lease_name,
        "identity": identity or socket.gethostname(),
        "leaseDurationSeconds": 15,
        "renewDeadlineSeconds": 10,
        "retryPeriodSeconds": 2,
    }


def resource_budget_payload() -> dict[str, Any]:
    return {
        "component": COMPONENT,
        "watchResource": WATCH_RESOURCE,
        "budget": RESOURCE_BUDGET,
        "measurement": {
            "tool": "kubectl top pod",
            "namespace": DEFAULT_NAMESPACE,
            "selector": CONTROLLER_SELECTOR,
            "requiresMetricsServer": True,
        },
    }


def resource_measure_command(namespace: str = DEFAULT_NAMESPACE) -> list[str]:
    return [
        "kubectl",
        "top",
        "pod",
        "-n",
        namespace,
        "-l",
        CONTROLLER_SELECTOR,
        "--containers",
    ]
