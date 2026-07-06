#!/usr/bin/env python3
"""Verify upstream N/N-1/N-2 local conformance suite."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "conformance" / "upstream-supported-minors.json"
DOC = ROOT / "docs" / "conformance.md"
COMPATIBILITY_DOC = ROOT / "docs" / "kubernetes-compatibility.md"
EXPECTED_MINORS = ("1.36", "1.35", "1.34")
REQUIRED_CHECKS = (
    "verify_crd_compatibility.py",
    "verify_crd_upgrade_fixtures.py",
    "verify_crd_explain_quality.py",
)


def run_script(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / script)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    fixture = json.loads(FIXTURE.read_text())
    doc = DOC.read_text()
    compatibility_doc = COMPATIBILITY_DOC.read_text()

    if tuple(fixture.get("upstreamMinors", [])) != EXPECTED_MINORS:
        errors.append("fixture upstreamMinors mismatch")
    if fixture.get("source") != "https://kubernetes.io/releases/version-skew-policy/":
        errors.append("fixture source mismatch")
    if fixture.get("sourceSnapshot") != "2026-07-06":
        errors.append("fixture source snapshot mismatch")
    for minor in EXPECTED_MINORS:
        if f"`{minor}`" not in doc:
            errors.append(f"conformance doc missing minor: {minor}")
        if f"`{minor}`" not in compatibility_doc:
            errors.append(f"compatibility doc missing minor: {minor}")
    for check in REQUIRED_CHECKS:
        if check not in doc:
            errors.append(f"conformance doc missing check: {check}")
        result = run_script(check)
        if result.returncode != 0:
            errors.append(f"{check} failed: {result.stderr.strip()}")

    if errors:
        print("conformance-suite: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("conformance-suite: passed")
    print("upstream-minors: 1.36, 1.35, 1.34")
    print("checks: crd-compatibility, crd-upgrade-fixtures, crd-explain-quality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
