#!/usr/bin/env python3
"""Verify Pluto evidence adapter fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "adapt_pluto_evidence.py"
PASS_FIXTURE = ROOT / "tests" / "fixtures" / "pluto" / "pass.json"
FAIL_FIXTURE = ROOT / "tests" / "fixtures" / "pluto" / "fail.json"
DOC = ROOT / "docs" / "policy-adapters.md"


def run_adapter(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(ADAPTER), str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    passed = run_adapter(PASS_FIXTURE)
    failed = run_adapter(FAIL_FIXTURE)

    if passed.returncode != 0:
        errors.append(f"pass fixture failed: {passed.stderr.strip()}")
        pass_evidence = {}
    else:
        pass_evidence = json.loads(passed.stdout)
    if failed.returncode == 0:
        errors.append("fail fixture unexpectedly passed")
        fail_evidence = {}
    else:
        fail_evidence = json.loads(failed.stdout)

    if pass_evidence.get("ok") is not True:
        errors.append("pass fixture evidence should be ok")
    if pass_evidence.get("reason") != "api-compatible":
        errors.append("pass fixture reason mismatch")
    if pass_evidence.get("deprecatedApiResults", {}).get("items") != 0:
        errors.append("pass fixture item count mismatch")

    if fail_evidence.get("ok") is not False:
        errors.append("fail fixture evidence should not be ok")
    if fail_evidence.get("reason") != "deprecated-api-found":
        errors.append("fail fixture reason mismatch")
    if fail_evidence.get("deprecatedApiResults", {}).get("removed") != 1:
        errors.append("fail fixture removed count mismatch")
    if fail_evidence.get("deprecatedApiResults", {}).get("deprecated") != 1:
        errors.append("fail fixture deprecated count mismatch")

    doc = DOC.read_text()
    for required in ("Pluto", "adapt_pluto_evidence.py", "pluto-deprecated-api", "does not run Pluto"):
        if required not in doc:
            errors.append(f"policy adapter docs missing: {required}")

    if errors:
        print("pluto-adapter: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("pluto-adapter: passed")
    print("pass-fixture: api-compatible")
    print("fail-fixture: deprecated-api-found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
