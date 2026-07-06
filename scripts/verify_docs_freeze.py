#!/usr/bin/env python3
"""Verify release-candidate documentation and public examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
    "README.md",
    "README.ko.md",
    "CHANGELOG.md",
    "LICENSE",
    "SECURITY.md",
    "docs/admission.md",
    "docs/api-freeze.md",
    "docs/collectors.md",
    "docs/controller.md",
    "docs/docs-freeze.md",
    "docs/interoperability.md",
    "docs/kubernetes-compatibility.md",
    "docs/policy-adapters.md",
    "docs/release-checklist.md",
    "docs/release-taskboard.md",
    "docs/roadmap.md",
    "docs/supply-chain.md",
    "docs/threat-model.md",
)
REQUIRED_README_SNIPPETS = (
    "Evidence-carrying operations for AI-assisted Kubernetes.",
    "python3 -B scripts/verify_release.py --version 0.2.0",
    "verify_docs_freeze.py",
    "no direct cluster write execution;",
)
REQUIRED_EXAMPLES = (
    "examples/read-pods.verified.capsule.json",
    "examples/scale-prod-deployment.capsule.json",
    "examples/apply-configmap.preflight.capsule.json",
    "examples/apply-configmap.diff.capsule.json",
    "examples/apply-configmap.rollback.capsule.json",
    "examples/configmap-demo.yaml",
    "examples/configmap-demo.rollback.yaml",
    "examples/operationcapsule-scale.yaml",
    "examples/mcp-client-config.json",
    "examples/agent-local-ci.runbook.md",
    "examples/agent-codex-workflow.runbook.md",
)
RUNBOOKS = (
    "examples/agent-local-ci.runbook.md",
    "examples/agent-codex-workflow.runbook.md",
)
UNSAFE_RUNBOOK_SNIPPETS = (
    "kubectl apply -f",
    "kubectl delete",
    "kubectl scale",
    "kubectl rollout restart",
)


def read_json(path: Path) -> Any:
    with path.open() as handle:
        return json.load(handle)


def verify_capsule(path: Path, errors: list[str]) -> None:
    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        errors.append(f"{path.relative_to(ROOT)} invalid JSON: {exc}")
        return
    if payload.get("apiVersion") != "kubeactuary.dev/v0alpha1":
        errors.append(f"{path.relative_to(ROOT)} apiVersion mismatch")
    if payload.get("kind") != "OperationCapsule":
        errors.append(f"{path.relative_to(ROOT)} kind mismatch")
    for field in ("metadata", "spec", "status"):
        if not isinstance(payload.get(field), dict):
            errors.append(f"{path.relative_to(ROOT)} missing object field: {field}")
    spec = payload.get("spec", {})
    if not isinstance(spec.get("requiredEvidence"), list):
        errors.append(f"{path.relative_to(ROOT)} missing requiredEvidence list")


def main() -> int:
    errors: list[str] = []

    for doc in REQUIRED_DOCS:
        if not (ROOT / doc).is_file():
            errors.append(f"missing doc: {doc}")

    readme = (ROOT / "README.md").read_text() if (ROOT / "README.md").is_file() else ""
    for snippet in REQUIRED_README_SNIPPETS:
        if snippet not in readme:
            errors.append(f"README.md missing: {snippet}")

    docs_freeze = ROOT / "docs" / "docs-freeze.md"
    if docs_freeze.is_file():
        text = docs_freeze.read_text()
        for snippet in ("public examples audit", "python3 -B scripts/verify_docs_freeze.py", "does not contact the cluster"):
            if snippet not in text:
                errors.append(f"docs-freeze.md missing: {snippet}")

    for example in REQUIRED_EXAMPLES:
        path = ROOT / example
        if not path.is_file():
            errors.append(f"missing example: {example}")
            continue
        if example.endswith(".capsule.json"):
            verify_capsule(path, errors)
        elif example == "examples/mcp-client-config.json":
            payload = read_json(path)
            server = payload.get("mcpServers", {}).get("kube-actuary", {})
            if server.get("args") != ["-B", "scripts/kube_actuary_mcp_server.py"]:
                errors.append("examples/mcp-client-config.json does not point to MCP server")
        elif example.endswith(".yaml"):
            text = path.read_text()
            if "apiVersion:" not in text or "kind:" not in text:
                errors.append(f"{example} missing apiVersion/kind")

    for runbook in RUNBOOKS:
        path = ROOT / runbook
        if not path.is_file():
            continue
        text = path.read_text()
        for snippet in UNSAFE_RUNBOOK_SNIPPETS:
            if snippet in text:
                errors.append(f"{runbook} must not instruct direct write: {snippet}")

    if errors:
        print("docs-freeze: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("docs-freeze: passed")
    print(f"docs: {len(REQUIRED_DOCS)} checked")
    print(f"public-examples: {len(REQUIRED_EXAMPLES)} checked")
    print("writes: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
