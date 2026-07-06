#!/usr/bin/env python3
"""Verify CRD upgrade and rollback fixtures without a live cluster."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "deploy" / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
ROLLBACK = ROOT / "deploy" / "crds" / "fixtures" / "operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml"
RUNBOOK = ROOT / "docs" / "crd-upgrade-rollback.md"

IDENTITY_SNIPPETS = (
    "apiVersion: apiextensions.k8s.io/v1",
    "kind: CustomResourceDefinition",
    "name: operationcapsules.ops.kubeactuary.dev",
    "group: ops.kubeactuary.dev",
    "scope: Namespaced",
    "plural: operationcapsules",
    "singular: operationcapsule",
    "kind: OperationCapsule",
    "name: v1alpha1",
    "served: true",
    "storage: true",
    "status: {}",
)
CURRENT_ONLY_SNIPPETS = (
    "pattern: ^sha256:[a-f0-9]{64}$",
    "conditions:",
    "EvidenceComplete",
    "RollbackReady",
    "reason:",
)
RUNBOOK_SNIPPETS = (
    "kubectl apply --server-side --dry-run=server",
    "deploy/crds/fixtures/operationcapsules.ops.kubeactuary.dev.v0.2.0.yaml",
    "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml",
    "rollback can reject",
)


def missing(text: str, snippets: tuple[str, ...]) -> list[str]:
    return [snippet for snippet in snippets if snippet not in text]


def main() -> int:
    errors: list[str] = []
    current = CURRENT.read_text()
    rollback = ROLLBACK.read_text()
    runbook = RUNBOOK.read_text()

    for label, text in (("current", current), ("rollback", rollback)):
        for snippet in missing(text, IDENTITY_SNIPPETS):
            errors.append(f"{label} CRD missing identity snippet: {snippet}")
    for snippet in missing(current, CURRENT_ONLY_SNIPPETS):
        errors.append(f"current CRD missing v0.3 status snippet: {snippet}")
    if "kubeactuary.dev/fixture-version: \"0.2.0\"" not in rollback:
        errors.append("rollback fixture missing fixture-version annotation")
    for snippet in CURRENT_ONLY_SNIPPETS:
        if snippet in rollback and snippet != "reason:":
            errors.append(f"rollback fixture unexpectedly contains current-only snippet: {snippet}")
    for snippet in missing(runbook, RUNBOOK_SNIPPETS):
        errors.append(f"runbook missing snippet: {snippet}")

    if errors:
        print("crd-upgrade-fixtures: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("crd-upgrade-fixtures: passed")
    print(f"current: {CURRENT.relative_to(ROOT)}")
    print(f"rollback: {ROLLBACK.relative_to(ROOT)}")
    print(f"runbook: {RUNBOOK.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
