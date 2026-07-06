#!/usr/bin/env python3
"""Verify security policy, threat model, and disclosure process docs."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECURITY = ROOT / "SECURITY.md"
THREAT_MODEL = ROOT / "docs" / "threat-model.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"


def require(text: str, snippets: tuple[str, ...], label: str, errors: list[str]) -> None:
    for snippet in snippets:
        if snippet not in text:
            errors.append(f"{label} missing: {snippet}")


def main() -> int:
    errors: list[str] = []
    security = SECURITY.read_text() if SECURITY.is_file() else ""
    threat_model = THREAT_MODEL.read_text() if THREAT_MODEL.is_file() else ""
    taskboard = TASKBOARD.read_text() if TASKBOARD.is_file() else ""

    require(
        security,
        (
            "Supported Versions",
            "Reporting a Vulnerability",
            "GitHub private vulnerability reporting",
            "Do not open a public issue with exploit details",
            "avoid direct Kubernetes write execution",
            "execute_approved_capsule",
        ),
        "SECURITY.md",
        errors,
    )
    require(
        threat_model,
        (
            "Assets",
            "Trust Boundaries",
            "In Scope",
            "Out of Scope",
            "Mitigations",
            "Residual Risk",
            "failurePolicy: Ignore",
        ),
        "threat model",
        errors,
    )
    if "Security policy, threat model, disclosure process" not in taskboard:
        errors.append("taskboard missing v0.9.1 security task")

    if errors:
        print("security-docs: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("security-docs: passed")
    print("security-policy: present")
    print("threat-model: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
