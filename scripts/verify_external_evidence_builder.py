#!/usr/bin/env python3
"""Verify supplemental external evidence builder behavior."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_external_evidence.py"
README = ROOT / "README.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"


def run_builder(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(BUILDER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        explain = tmpdir / "explain.txt"
        explain.write_text("KIND: OperationCapsule\nFIELDS:\n  spec\n  status\n")
        explain_result = run_builder("--kind", "kubectl-explain", "--source", str(explain))

        budget = tmpdir / "kubectl-top.txt"
        budget.write_text("POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n")
        budget_result = run_builder("--kind", "controller-resource-budget", "--source", str(budget))

        loop = tmpdir / "loop.json"
        loop.write_text(
            json.dumps(
                {
                    "mode": "server-dry-run-loop",
                    "writeExecution": "disabled",
                    "readExecution": "kubectl-get",
                    "failed": 0,
                    "ticks": [],
                }
            )
        )
        output = tmpdir / "loop-evidence.json"
        loop_result = run_builder("--kind", "controller-live-loop", "--source", str(loop), "--output", str(output))

        bad_budget = tmpdir / "bad-kubectl-top.txt"
        bad_budget.write_text("POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 70m 90Mi\n")
        bad_result = run_builder("--kind", "controller-resource-budget", "--source", str(bad_budget))

    payloads = []
    for name, result in (("explain", explain_result), ("budget", budget_result)):
        if result.returncode != 0:
            errors.append(f"{name} evidence build failed: {result.stderr.strip() or result.stdout.strip()}")
            continue
        try:
            payloads.append(json.loads(result.stdout))
        except json.JSONDecodeError as exc:
            errors.append(f"{name} evidence output must parse as JSON: {exc}")

    if loop_result.returncode != 0:
        errors.append(f"loop evidence build failed: {loop_result.stderr.strip() or loop_result.stdout.strip()}")
    if "external-evidence: wrote" not in loop_result.stdout:
        errors.append("builder must report output file writes")
    if bad_result.returncode == 0:
        errors.append("failing resource budget sample must return non-zero")
    if "controller resource budget sample failed" not in bad_result.stdout:
        errors.append("failing resource budget evidence must explain failure")

    for payload in payloads:
        if payload.get("schemaVersion") != "kube-actuary.external-evidence.v1":
            errors.append("supplemental evidence schemaVersion mismatch")
        if payload.get("ok") is not True:
            errors.append("passing supplemental evidence must set ok=true")
        source = payload.get("source", {})
        if len(str(source.get("sha256", ""))) != 64:
            errors.append("supplemental evidence source must include sha256")

    for snippet in ("build_external_evidence.py", "kube-actuary.external-evidence.v1"):
        if snippet not in README.read_text():
            errors.append(f"README missing external evidence builder detail: {snippet}")
        if snippet not in LIVE_VALIDATION.read_text():
            errors.append(f"live validation doc missing external evidence builder detail: {snippet}")

    if errors:
        print("external-evidence-builder: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("external-evidence-builder: passed")
    print("kinds: 3")
    print("failure-mode: nonzero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
