#!/usr/bin/env python3
"""Verify optional controller deployment seed without contacting a cluster."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "bin" / "kube-actuary-controller"
DEPLOYMENT = ROOT / "deploy" / "controller" / "deployment.yaml"
NAMESPACE_COPY = ROOT / "deploy" / "kustomize" / "overlays" / "controller-namespace" / "controller" / "deployment.yaml"
CLUSTER_COPY = ROOT / "deploy" / "kustomize" / "overlays" / "controller-cluster" / "controller" / "deployment.yaml"
HELM_TEMPLATE = ROOT / "charts" / "kubeactuary" / "templates" / "controller-deployment.yaml"
VALUES = ROOT / "charts" / "kubeactuary" / "values.yaml"
DOC = ROOT / "docs" / "controller.md"


REQUIRED_DEPLOYMENT_SNIPPETS = (
    "kind: Deployment",
    "replicas: 1",
    "serviceAccountName: kubeactuary-controller",
    "automountServiceAccountToken: false",
    "image: ghcr.io/kubeactuary/kubeactuary-controller:0.2.0",
    "- serve",
    "- --host",
    "- 0.0.0.0",
    "- --port",
    "- \"8080\"",
    "path: /healthz",
    "path: /readyz",
    "cpu: 10m",
    "memory: 32Mi",
    "cpu: 50m",
    "memory: 64Mi",
    "runAsNonRoot: true",
    "allowPrivilegeEscalation: false",
    "readOnlyRootFilesystem: true",
    "- ALL",
)
FORBIDDEN_DEPLOYMENT_SNIPPETS = (
    "privileged: true",
    "hostNetwork: true",
    "resources: [\"*\"]",
    "verbs: [\"*\"]",
    "kubectl apply",
    "kubectl delete",
)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    deployment = DEPLOYMENT.read_text()

    for snippet in REQUIRED_DEPLOYMENT_SNIPPETS:
        require(snippet in deployment, f"deployment missing: {snippet}", errors)
    for snippet in FORBIDDEN_DEPLOYMENT_SNIPPETS:
        require(snippet not in deployment, f"deployment contains forbidden snippet: {snippet}", errors)

    require(NAMESPACE_COPY.read_text() == deployment, "namespace Kustomize deployment copy differs", errors)
    require(CLUSTER_COPY.read_text() == deployment, "cluster Kustomize deployment copy differs", errors)

    helm = HELM_TEMPLATE.read_text()
    for snippet in (
        "kind: Deployment",
        "automountServiceAccountToken: false",
        "/app/bin/kube-actuary-controller",
        "- serve",
        "/healthz",
        "/readyz",
        "readOnlyRootFilesystem: true",
    ):
        require(snippet in helm, f"Helm deployment template missing: {snippet}", errors)
    values = VALUES.read_text()
    for snippet in ("enabled: false", "repository: ghcr.io/kubeactuary/kubeactuary-controller", "cpu: 10m", "memory: 64Mi"):
        require(snippet in values, f"Helm values missing: {snippet}", errors)

    serve = subprocess.run(
        [sys.executable, "-B", str(CONTROLLER), "serve", "--print-config"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if serve.returncode != 0:
        errors.append(f"serve --print-config failed: {serve.stderr.strip()}")
    else:
        config = json.loads(serve.stdout)
        if config.get("clusterAccess") != "none":
            errors.append("serve config must not require cluster access")
        for path in ("/healthz", "/readyz", "/metrics"):
            if path not in config.get("paths", []):
                errors.append(f"serve config missing path: {path}")

    doc = DOC.read_text()
    for snippet in ("Deployment seed", "serve", "/healthz", "/readyz", "/metrics", "automountServiceAccountToken: false"):
        require(snippet in doc, f"controller doc missing deployment contract: {snippet}", errors)

    if errors:
        print("controller-deployment: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-deployment: passed")
    print("runtime: serve")
    print("probes: healthz, readyz")
    print("resources: 10m/32Mi requests, 50m/64Mi limits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
