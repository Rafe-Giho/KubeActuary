#!/usr/bin/env python3
"""Verify admission identity selector and annotation requirements."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "scripts" / "evaluate_admission_review.py"
FIXTURES = ROOT / "tests" / "fixtures" / "admission"
DOC = ROOT / "docs" / "admission.md"
CASES = (
    ("allow-non-ai.json", True, "identity-not-selected"),
    ("allow-ai-annotated.json", True, "annotations-present"),
    ("deny-ai-missing-capsule.json", False, "missing-kubeactuary-annotations"),
    ("deny-ai-missing-digest.json", False, "missing-kubeactuary-annotations"),
)


def run_case(name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(EVALUATOR), str(FIXTURES / name)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    for fixture, expected_allowed, expected_reason in CASES:
        result = run_case(fixture)
        if expected_allowed and result.returncode != 0:
            errors.append(f"{fixture} unexpectedly denied: {result.stderr.strip()}")
        if not expected_allowed and result.returncode == 0:
            errors.append(f"{fixture} unexpectedly allowed")
        try:
            decision = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"{fixture} did not emit JSON: {exc}")
            continue
        if decision.get("allowed") is not expected_allowed:
            errors.append(f"{fixture} allowed mismatch: {decision.get('allowed')!r}")
        if decision.get("reason") != expected_reason:
            errors.append(f"{fixture} reason mismatch: {decision.get('reason')!r}")

    doc = DOC.read_text()
    for required in (
        "kubeactuary.dev/ai-writers",
        "system:serviceaccount:ai-agents:",
        "kubeactuary.dev/capsule",
        "kubeactuary.dev/capsule-digest",
    ):
        if required not in doc:
            errors.append(f"admission docs missing: {required}")

    if errors:
        print("admission-policy: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("admission-policy: passed")
    print("allow-fixtures: 2")
    print("deny-fixtures: 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
