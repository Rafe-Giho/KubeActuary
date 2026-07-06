#!/usr/bin/env python3
"""Verify common adapter evidence contract across fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEVERITIES = {"none", "info", "warning", "error", "critical"}
COMMON_FIELDS = {"id", "ok", "summary", "actor", "collector", "reason", "severity", "sourceRef"}
CASES = (
    ("kyverno", "scripts/adapt_kyverno_evidence.py", "tests/fixtures/kyverno/pass.json", True),
    ("kyverno", "scripts/adapt_kyverno_evidence.py", "tests/fixtures/kyverno/fail.json", False),
    ("opa", "scripts/adapt_opa_evidence.py", "tests/fixtures/opa/pass.json", True),
    ("opa", "scripts/adapt_opa_evidence.py", "tests/fixtures/opa/fail.json", False),
    ("kube-linter", "scripts/adapt_kube_linter_evidence.py", "tests/fixtures/kube-linter/pass.json", True),
    ("kube-linter", "scripts/adapt_kube_linter_evidence.py", "tests/fixtures/kube-linter/fail.json", False),
    ("kube-score", "scripts/adapt_kube_score_evidence.py", "tests/fixtures/kube-score/pass.json", True),
    ("kube-score", "scripts/adapt_kube_score_evidence.py", "tests/fixtures/kube-score/fail.json", False),
    ("pluto", "scripts/adapt_pluto_evidence.py", "tests/fixtures/pluto/pass.json", True),
    ("pluto", "scripts/adapt_pluto_evidence.py", "tests/fixtures/pluto/fail.json", False),
)


def run_adapter(script: str, fixture: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / script), str(ROOT / fixture)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def validate_case(name: str, script: str, fixture: str, expected_ok: bool) -> list[str]:
    errors: list[str] = []
    result = run_adapter(script, fixture)
    if expected_ok and result.returncode != 0:
        errors.append(f"{name} pass fixture returned {result.returncode}: {result.stderr.strip()}")
    if not expected_ok and result.returncode == 0:
        errors.append(f"{name} fail fixture unexpectedly returned 0")

    try:
        evidence = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [*errors, f"{name} emitted invalid JSON: {exc}"]

    missing = sorted(COMMON_FIELDS - evidence.keys())
    if missing:
        errors.append(f"{name} evidence missing fields: {', '.join(missing)}")
    if evidence.get("collector") != name:
        errors.append(f"{name} collector mismatch: {evidence.get('collector')!r}")
    if evidence.get("ok") is not expected_ok:
        errors.append(f"{name} ok mismatch: {evidence.get('ok')!r}")
    if not isinstance(evidence.get("summary"), str) or not evidence.get("summary"):
        errors.append(f"{name} summary must be a non-empty string")
    if not isinstance(evidence.get("reason"), str) or not evidence.get("reason"):
        errors.append(f"{name} reason must be a non-empty string")
    if evidence.get("severity") not in SEVERITIES:
        errors.append(f"{name} severity not normalized: {evidence.get('severity')!r}")
    if expected_ok and evidence.get("severity") != "none":
        errors.append(f"{name} pass fixture severity should be none")
    if not expected_ok and evidence.get("severity") == "none":
        errors.append(f"{name} fail fixture severity should not be none")
    return errors


def main() -> int:
    errors: list[str] = []
    for case in CASES:
        errors.extend(validate_case(*case))

    if errors:
        print("adapter-contract: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("adapter-contract: passed")
    print("fixtures: 10")
    print("severity: normalized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
