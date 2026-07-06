#!/usr/bin/env python3
"""Verify the Helm chart contract without requiring Helm."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "charts" / "kubeactuary"
VERSION = (ROOT / "VERSION").read_text().strip()
CRD = ROOT / "deploy" / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
CHART_CRD = CHART / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
VALUES = CHART / "values.yaml"
TEMPLATE = CHART / "templates" / "controller-rbac.yaml"
DEPLOYMENT_TEMPLATE = CHART / "templates" / "controller-deployment.yaml"


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    chart_yaml = (CHART / "Chart.yaml").read_text()
    values = VALUES.read_text()
    template = TEMPLATE.read_text()
    deployment_template = DEPLOYMENT_TEMPLATE.read_text()

    require("apiVersion: v2" in chart_yaml, "Chart.yaml must use Helm v2 schema", errors)
    require("name: kubeactuary" in chart_yaml, "Chart.yaml name mismatch", errors)
    require(f"version: {VERSION}" in chart_yaml, "Chart.yaml version must match VERSION", errors)
    require(f'appVersion: "{VERSION}"' in chart_yaml, "Chart.yaml appVersion must match VERSION", errors)
    require(CHART_CRD.read_text() == CRD.read_text(), "chart CRD must match deploy CRD", errors)

    require("enabled: false" in values, "controller must be disabled by default", errors)
    require("scope: namespace" in values, "namespace-scoped RBAC must be default", errors)
    require("repository: ghcr.io/kubeactuary/kubeactuary-controller" in values, "controller image repository missing", errors)
    require("cpu: 10m" in values and "memory: 64Mi" in values, "controller resource budget missing", errors)

    for required in (
        "kind: ServiceAccount",
        "kind: Role",
        "kind: RoleBinding",
        "kind: ClusterRole",
        "kind: ClusterRoleBinding",
        'resources: ["operationcapsules"]',
        'resources: ["operationcapsules/status"]',
        'verbs: ["get", "list", "watch"]',
        'verbs: ["get", "patch", "update"]',
    ):
        require(required in template, f"controller RBAC template missing: {required}", errors)
    for forbidden in ('resources: ["*"]', 'apiGroups: ["*"]', 'verbs: ["*"]', "kind: Deployment"):
        require(forbidden not in template, f"controller RBAC template contains forbidden field: {forbidden}", errors)
    for required in (
        "kind: Deployment",
        "automountServiceAccountToken: false",
        "- serve",
        "/healthz",
        "/readyz",
        "readOnlyRootFilesystem: true",
    ):
        require(required in deployment_template, f"controller deployment template missing: {required}", errors)

    helm = shutil.which("helm")
    helm_status = "not-found"
    if helm:
        result = subprocess.run(
            [helm, "template", "kubeactuary", str(CHART), "--set", "controller.enabled=true"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        helm_status = "passed" if result.returncode == 0 else "failed"
        if result.returncode != 0:
            errors.append(f"helm template failed: {result.stderr.strip()}")

    if errors:
        print("helm-chart: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("helm-chart: passed")
    print("crd: included")
    print("controller: optional")
    print(f"helm-template: {helm_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
