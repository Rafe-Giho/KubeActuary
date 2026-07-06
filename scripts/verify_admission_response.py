#!/usr/bin/env python3
"""Verify AdmissionReview response and audit annotation generation."""

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
    ("allow-ai-annotated.json", True, "annotations-present"),
    ("deny-ai-missing-digest.json", False, "missing-kubeactuary-annotations"),
)


def run_case(fixture: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(EVALUATOR), str(FIXTURES / fixture), "--response"],
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
            review = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"{fixture} did not emit AdmissionReview JSON: {exc}")
            continue
        if review.get("apiVersion") != "admission.k8s.io/v1":
            errors.append(f"{fixture} apiVersion mismatch")
        if review.get("kind") != "AdmissionReview":
            errors.append(f"{fixture} kind mismatch")
        response = review.get("response", {})
        if response.get("allowed") is not expected_allowed:
            errors.append(f"{fixture} allowed mismatch")
        if response.get("status", {}).get("reason") != expected_reason:
            errors.append(f"{fixture} reason mismatch")
        annotations = response.get("auditAnnotations", {})
        for key in ("kubeactuary.dev/decision", "kubeactuary.dev/reason"):
            if not annotations.get(key):
                errors.append(f"{fixture} missing audit annotation: {key}")

    doc = DOC.read_text()
    for snippet in ("--response", "AdmissionReview response", "auditAnnotations", "verify_admission_response.py"):
        if snippet not in doc:
            errors.append(f"admission docs missing response contract: {snippet}")

    if errors:
        print("admission-response: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("admission-response: passed")
    print("responses: 2")
    print("auditAnnotations: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
