#!/usr/bin/env python3
"""Verify admission capsule digest and gate tamper fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "kube-actuary"
FIXTURES = ROOT / "tests" / "fixtures" / "admission"
CAPSULES = {
    "opcap-example-read-pods": ROOT / "examples" / "read-pods.verified.capsule.json",
    "opcap-example-scale-prod": ROOT / "examples" / "scale-prod-deployment.capsule.json",
}
CAPSULE_ANNOTATION = "kubeactuary.dev/capsule"
DIGEST_ANNOTATION = "kubeactuary.dev/capsule-digest"
CASES = (
    ("allow-ai-valid-gate.json", True, "gate-open"),
    ("deny-ai-bad-digest.json", False, "digest-mismatch"),
    ("deny-ai-closed-gate.json", False, "gate-closed"),
)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def object_annotations(review: dict[str, Any]) -> dict[str, str]:
    request = review.get("request")
    if not isinstance(request, dict):
        return {}
    obj = request.get("object")
    if not isinstance(obj, dict):
        obj = request.get("oldObject")
    if not isinstance(obj, dict):
        return {}
    metadata = obj.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    annotations = metadata.get("annotations")
    if not isinstance(annotations, dict):
        return {}
    return {str(key): str(value) for key, value in annotations.items()}


def capsule_digest(path: Path) -> str:
    result = run_cli("digest", str(path))
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def gate_open(path: Path) -> bool:
    return run_cli("gate", str(path)).returncode == 0


def evaluate(path: Path) -> dict[str, Any]:
    review = json.loads(path.read_text())
    annotations = object_annotations(review)
    capsule_id = annotations.get(CAPSULE_ANNOTATION, "")
    observed_digest = annotations.get(DIGEST_ANNOTATION, "")
    capsule_path = CAPSULES.get(capsule_id)
    if capsule_path is None:
        return {"allowed": False, "reason": "unknown-capsule"}

    expected_digest = capsule_digest(capsule_path)
    if observed_digest != expected_digest:
        return {"allowed": False, "reason": "digest-mismatch"}
    if not gate_open(capsule_path):
        return {"allowed": False, "reason": "gate-closed"}
    return {"allowed": True, "reason": "gate-open"}


def main() -> int:
    errors: list[str] = []
    for fixture, expected_allowed, expected_reason in CASES:
        decision = evaluate(FIXTURES / fixture)
        if decision.get("allowed") is not expected_allowed:
            errors.append(f"{fixture} allowed mismatch: {decision.get('allowed')!r}")
        if decision.get("reason") != expected_reason:
            errors.append(f"{fixture} reason mismatch: {decision.get('reason')!r}")

    if errors:
        print("admission-digest-gate: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("admission-digest-gate: passed")
    print("allow-fixtures: 1")
    print("tamper-fixtures: 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
