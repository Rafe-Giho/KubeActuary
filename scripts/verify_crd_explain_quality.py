#!/usr/bin/env python3
"""Verify kubectl explain quality for the KubeActuary CRD."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRD = ROOT / "deploy" / "crds" / "operationcapsules.ops.kubeactuary.dev.yaml"
DOC = ROOT / "docs" / "kubectl-explain.md"

DESCRIPTION_SNIPPETS = (
    "description: OperationCapsule records a proposed Kubernetes operation, required evidence, and gate status.",
    "description: Desired operation contract and evidence requirements.",
    "description: Human-readable reason for the proposed operation.",
    "description: Principal that drafted or owns the operation capsule.",
    "description: Proposed Kubernetes action. KubeActuary records this action but does not execute it.",
    "description: Local blast-radius classification for the proposed action.",
    "description: Evidence identifiers that must be attached successfully before the gate opens.",
    "description: Embedded evidence summaries attached by collectors, reviewers, or external tools.",
    "description: Planned post-change checks to run after an external executor applies the operation.",
    "description: Explicit rollback plan or manifest reference for the operation.",
    "description: Derived gate state, missing evidence, failed evidence, digest, and conditions.",
    "description: High-level lifecycle phase derived from evidence and gate state.",
    "description: Open when all required evidence exists and no required evidence failed.",
    "description: SHA-256 digest of capsule identity and spec for audit references.",
    "description: Kubernetes-style status conditions derived from the evidence gate.",
)

EXPLAIN_COMMANDS = (
    "kubectl explain operationcapsule",
    "kubectl explain operationcapsule.spec",
    "kubectl explain operationcapsule.spec.proposedAction",
    "kubectl explain operationcapsule.spec.evidence",
    "kubectl explain operationcapsule.spec.rollback",
    "kubectl explain operationcapsule.status",
    "kubectl explain operationcapsule.status.conditions",
)


def missing(text: str, snippets: tuple[str, ...]) -> list[str]:
    return [snippet for snippet in snippets if snippet not in text]


def main() -> int:
    errors: list[str] = []
    crd = CRD.read_text()
    doc = DOC.read_text()

    for snippet in missing(crd, DESCRIPTION_SNIPPETS):
        errors.append(f"crd missing description: {snippet}")
    for command in missing(doc, EXPLAIN_COMMANDS):
        errors.append(f"doc missing explain command: {command}")
    if "KubeActuary records but does not execute" not in doc:
        errors.append("doc missing non-execution boundary")

    if errors:
        print("crd-explain-quality: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("crd-explain-quality: passed")
    print(f"descriptions: {len(DESCRIPTION_SNIPPETS)}")
    print(f"commands: {len(EXPLAIN_COMMANDS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
