#!/usr/bin/env python3
"""Verify admission audit annotation fixtures and incident runbook."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "admission"
RUNBOOK = ROOT / "docs" / "admission-incident-runbook.md"
DOC = ROOT / "docs" / "admission.md"
AUDIT_KEYS = (
    "kubeactuary.dev/capsule",
    "kubeactuary.dev/capsule-digest",
    "kubeactuary.dev/gate",
    "kubeactuary.dev/decision",
    "kubeactuary.dev/reason",
)
CASES = (
    ("audit-allow.json", "allow", "open"),
    ("audit-deny.json", "deny", "closed"),
)


def audit_annotations(payload: dict[str, Any]) -> dict[str, str]:
    response = payload.get("response")
    if not isinstance(response, dict):
        return {}
    annotations = response.get("auditAnnotations")
    if not isinstance(annotations, dict):
        return {}
    return {str(key): str(value) for key, value in annotations.items()}


def main() -> int:
    errors: list[str] = []
    for fixture, expected_decision, expected_gate in CASES:
        payload = json.loads((FIXTURES / fixture).read_text())
        annotations = audit_annotations(payload)
        for key in AUDIT_KEYS:
            if not annotations.get(key):
                errors.append(f"{fixture} missing audit annotation: {key}")
        if annotations.get("kubeactuary.dev/decision") != expected_decision:
            errors.append(f"{fixture} decision mismatch")
        if annotations.get("kubeactuary.dev/gate") != expected_gate:
            errors.append(f"{fixture} gate mismatch")

    runbook = RUNBOOK.read_text() if RUNBOOK.is_file() else ""
    for required in (
        "Required audit annotations",
        "kubeactuary.dev/capsule-digest",
        "bin/kube-actuary digest",
        "bin/kube-actuary gate",
        "Do not retry or apply",
    ):
        if required not in runbook:
            errors.append(f"incident runbook missing: {required}")

    doc = DOC.read_text() if DOC.is_file() else ""
    if "admission-incident-runbook.md" not in doc:
        errors.append("admission docs missing incident runbook link")

    if errors:
        print("admission-audit: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("admission-audit: passed")
    print("audit-fixtures: 2")
    print("runbook: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
