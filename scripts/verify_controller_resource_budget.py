#!/usr/bin/env python3
"""Verify controller resource budget contracts and measurement harness."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "bin" / "kube-actuary-controller"
MEASURE = ROOT / "scripts" / "measure_controller_resources.py"
DOC = ROOT / "docs" / "controller.md"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(CONTROLLER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []

    budget = run("resource-budget")
    if budget.returncode != 0:
        errors.append(f"resource-budget failed: {budget.stderr.strip()}")
        payload = {}
    else:
        payload = json.loads(budget.stdout)
    budget_values = payload.get("budget", {})
    if budget_values.get("idleCpuMillicoresLessThan") != 50:
        errors.append("CPU budget must be less than 50m")
    if budget_values.get("idleMemoryMiLessThan") != 64:
        errors.append("memory budget must be less than 64Mi")
    if budget_values.get("requests") != {"cpu": "10m", "memory": "32Mi"}:
        errors.append("resource requests changed unexpectedly")
    if budget_values.get("limits") != {"cpu": "50m", "memory": "64Mi"}:
        errors.append("resource limits changed unexpectedly")

    measure_command = run("measure-command")
    expected_command = (
        "kubectl top pod -n kubeactuary-system -l "
        "app.kubernetes.io/name=kubeactuary,app.kubernetes.io/component=controller --containers"
    )
    if measure_command.stdout.strip() != expected_command:
        errors.append(f"unexpected measure command: {measure_command.stdout.strip()}")

    with tempfile.TemporaryDirectory() as tmpdir:
        sample = Path(tmpdir) / "kubectl-top.txt"
        sample.write_text(
            "POD NAME CPU(cores) MEMORY(bytes)\n"
            "controller-0 controller 12m 41Mi\n"
            "controller-0 sidecar 8m 28Mi\n"
        )
        passed = subprocess.run(
            [sys.executable, "-B", str(MEASURE), "--sample", str(sample)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        structured = subprocess.run(
            [sys.executable, "-B", str(MEASURE), "--sample", str(sample), "--format", "json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        sample.write_text("POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 55m 65Mi\n")
        failed = subprocess.run(
            [sys.executable, "-B", str(MEASURE), "--sample", str(sample)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    if structured.returncode != 0:
        errors.append("structured measurement sample did not pass")
        structured_payload = {}
    else:
        structured_payload = json.loads(structured.stdout)
    if passed.returncode != 0 or "resource-measurement: passed" not in passed.stdout:
        errors.append("passing sample did not pass budget measurement")
    if "sample-count: 2" not in passed.stdout:
        errors.append("text measurement must report sample count")
    if structured_payload.get("schemaVersion") != "kube-actuary.controller-resource-measurement.v1":
        errors.append("structured measurement schema version mismatch")
    if structured_payload.get("sampleCount") != 2:
        errors.append("structured measurement must preserve sample count")
    if structured_payload.get("observed") != {"cpuMillicores": 12, "memoryMi": 41}:
        errors.append("structured measurement must preserve observed maxima")
    if structured_payload.get("budget") != {"cpuMillicoresLessThan": 50, "memoryMiLessThan": 64}:
        errors.append("structured measurement must preserve budget values")
    if failed.returncode == 0 or "resource-measurement: failed" not in failed.stdout:
        errors.append("failing sample did not fail budget measurement")

    doc = DOC.read_text()
    for required in ("idle <50m CPU", "<64Mi memory", "measure_controller_resources.py"):
        if required not in doc:
            errors.append(f"controller doc missing resource budget detail: {required}")

    if errors:
        print("controller-resource-budget: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("controller-resource-budget: passed")
    print("idle-cpu-budget: <50m")
    print("idle-memory-budget: <64Mi")
    print("measurement-harness: kubectl top")
    print("measurement-format: text,json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
