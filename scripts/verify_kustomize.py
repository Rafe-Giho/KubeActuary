#!/usr/bin/env python3
"""Verify Kustomize base and overlays."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "deploy" / "kustomize" / "base"
NAMESPACE_OVERLAY = ROOT / "deploy" / "kustomize" / "overlays" / "controller-namespace"
CLUSTER_OVERLAY = ROOT / "deploy" / "kustomize" / "overlays" / "controller-cluster"
DOC = ROOT / "docs" / "kustomize.md"

CANONICAL_CRD = ROOT / "deploy" / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
KUSTOMIZE_CRD = BASE / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
CANONICAL_NAMESPACE_RBAC = ROOT / "deploy" / "controller" / "namespace-scoped-rbac.yaml"
KUSTOMIZE_NAMESPACE_RBAC = NAMESPACE_OVERLAY / "controller" / "namespace-scoped-rbac.yaml"
CANONICAL_CLUSTER_RBAC = ROOT / "deploy" / "controller" / "cluster-scoped-rbac.yaml"
KUSTOMIZE_CLUSTER_RBAC = CLUSTER_OVERLAY / "controller" / "cluster-scoped-rbac.yaml"


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def render(path: Path, errors: list[str]) -> str:
    kubectl = shutil.which("kubectl")
    if not kubectl:
        errors.append("kubectl not found")
        return ""
    result = subprocess.run(
        [kubectl, "kustomize", str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        errors.append(f"kubectl kustomize failed for {path}: {result.stderr.strip()}")
        return ""
    return result.stdout


def verify_render(name: str, output: str, expected: tuple[str, ...], forbidden: tuple[str, ...], errors: list[str]) -> None:
    for text in expected:
        require(text in output, f"{name}: rendered output missing {text}", errors)
    for text in forbidden:
        require(text not in output, f"{name}: rendered output contains forbidden {text}", errors)


def main() -> int:
    errors: list[str] = []

    require(KUSTOMIZE_CRD.read_text() == CANONICAL_CRD.read_text(), "Kustomize CRD copy differs from canonical CRD", errors)
    require(
        KUSTOMIZE_NAMESPACE_RBAC.read_text() == CANONICAL_NAMESPACE_RBAC.read_text(),
        "Kustomize namespace RBAC copy differs from canonical RBAC",
        errors,
    )
    require(
        KUSTOMIZE_CLUSTER_RBAC.read_text() == CANONICAL_CLUSTER_RBAC.read_text(),
        "Kustomize cluster RBAC copy differs from canonical RBAC",
        errors,
    )

    base = render(BASE, errors)
    namespace = render(NAMESPACE_OVERLAY, errors)
    cluster = render(CLUSTER_OVERLAY, errors)

    verify_render(
        "base",
        base,
        ("kind: CustomResourceDefinition", "name: operationcapsules.ops.kubeactuary.dev"),
        ("kind: Deployment", "kind: Role", "kind: ClusterRole"),
        errors,
    )
    verify_render(
        "namespace",
        namespace,
        (
            "kind: CustomResourceDefinition",
            "kind: ServiceAccount",
            "kind: Role",
            "kind: RoleBinding",
            "- operationcapsules",
            "- operationcapsules/status",
            "- get",
            "- list",
            "- watch",
            "- patch",
            "- update",
        ),
        ("kind: Deployment", "resources: ['*']", "verbs: ['*']", "apiGroups: ['*']"),
        errors,
    )
    verify_render(
        "cluster",
        cluster,
        (
            "kind: CustomResourceDefinition",
            "kind: ServiceAccount",
            "kind: ClusterRole",
            "kind: ClusterRoleBinding",
            "- operationcapsules",
            "- operationcapsules/status",
            "- get",
            "- list",
            "- watch",
            "- patch",
            "- update",
        ),
        ("kind: Deployment", "resources: ['*']", "verbs: ['*']", "apiGroups: ['*']"),
        errors,
    )

    doc = DOC.read_text()
    for required in ("kubectl kustomize", "controller-namespace", "controller-cluster", "OperationCapsule"):
        require(required in doc, f"Kustomize docs missing {required}", errors)

    if errors:
        print("kustomize: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("kustomize: passed")
    print("base: crd")
    print("overlay: controller-namespace")
    print("overlay: controller-cluster")
    return 0


if __name__ == "__main__":
    sys.exit(main())
