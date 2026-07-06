#!/usr/bin/env python3
"""Offline CRD compatibility smoke checks for KubeActuary."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRD = ROOT / "deploy" / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
DOC = ROOT / "docs" / "kubernetes-compatibility.md"

UPSTREAM_MINORS = ("1.36", "1.35", "1.34")
MANAGED_SOURCES = (
    "https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html",
    "https://cloud.google.com/kubernetes-engine/docs/release-schedule",
    "https://learn.microsoft.com/en-us/azure/aks/supported-kubernetes-versions",
)
CRD_REQUIRED_SNIPPETS = (
    "apiVersion: apiextensions.k8s.io/v1",
    "kind: CustomResourceDefinition",
    "name: operationcapsules.ops.kubeactuary.dev",
    "scope: Namespaced",
    "name: v1alpha1",
    "subresources:",
    "status: {}",
    "proposedAction:",
    "requiredEvidence:",
    "evidence:",
    "postChecks:",
    "rollback:",
    "missingEvidence:",
    "failedEvidence:",
    "conditions:",
    "EvidenceComplete",
    "GateOpen",
    "Blocked",
    "RollbackReady",
    "Expired",
)


def missing_snippets(text: str, snippets: tuple[str, ...]) -> list[str]:
    return [snippet for snippet in snippets if snippet not in text]


def main() -> int:
    errors: list[str] = []
    crd_text = CRD.read_text()
    doc_text = DOC.read_text()

    for snippet in missing_snippets(crd_text, CRD_REQUIRED_SNIPPETS):
        errors.append(f"crd missing: {snippet}")
    for minor in UPSTREAM_MINORS:
        if f"`{minor}`" not in doc_text:
            errors.append(f"compatibility doc missing upstream minor: {minor}")
    for source in MANAGED_SOURCES:
        if source not in doc_text:
            errors.append(f"compatibility doc missing source: {source}")
    if "Source snapshot: 2026-07-06." not in doc_text:
        errors.append("compatibility doc missing source snapshot date")

    if errors:
        print("crd-compatibility: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("crd-compatibility: passed")
    print(f"upstream-minors: {', '.join(UPSTREAM_MINORS)}")
    print("managed-sources: eks, gke, aks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
