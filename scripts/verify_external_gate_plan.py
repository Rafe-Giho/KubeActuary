#!/usr/bin/env python3
"""Verify the generated external gate plan stays aligned with the taskboard."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_external_gate_plan.py"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
README = ROOT / "README.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GENERATOR), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    json_result = run_generator("--format", "json")
    markdown_result = run_generator("--format", "markdown")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "external-gates.json"
        write_result = run_generator("--output", str(output))
        if write_result.returncode != 0 or not output.is_file():
            errors.append("generator must write requested output path")

    if json_result.returncode != 0:
        errors.append(f"json generation failed: {json_result.stderr.strip()}")
        plan = {}
    else:
        try:
            plan = json.loads(json_result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"json output must parse: {exc}")
            plan = {}

    if markdown_result.returncode != 0:
        errors.append(f"markdown generation failed: {markdown_result.stderr.strip()}")
    if "# External Verification Gate Plan" not in markdown_result.stdout:
        errors.append("markdown output missing heading")

    summary = plan.get("summary", {})
    gates = plan.get("gates", [])
    if plan.get("schemaVersion") != "kube-actuary.external-gate-plan.v1":
        errors.append("external gate plan schemaVersion mismatch")
    if summary.get("verify") != 0:
        errors.append(f"expected zero VERIFY gates after live blockers are accepted, got {summary.get('verify')!r}")
    if summary.get("blocked") != 16:
        errors.append(f"expected 16 BLOCKED gates, got {summary.get('blocked')!r}")
    if summary.get("doing") != 0 or summary.get("todo") != 0:
        errors.append("external gate plan must not leave DOING or TODO rows")
    if not isinstance(gates, list) or len(gates) != 16:
        errors.append("external gate plan must list each external blocked row")
    if any(gate.get("status") != "BLOCKED" for gate in gates if isinstance(gate, dict)):
        errors.append("external gate plan must preserve BLOCKED gate status")

    kinds = {gate.get("kind") for gate in gates if isinstance(gate, dict)}
    for expected in (
        "lightweight-cluster",
        "managed-kubernetes",
        "helm",
        "krew",
        "admission",
        "controller-resource-budget",
        "crd",
    ):
        if expected not in kinds:
            errors.append(f"external gate plan missing kind: {expected}")

    commands = "\n".join(
        command
        for gate in gates
        if isinstance(gate, dict)
        for command in gate.get("recommendedCommands", [])
    )
    for snippet in (
        "run_lightweight_cluster_smoke.py --provider kind",
        "run_managed_kubernetes_smoke.py --provider eks",
        "run_helm_smoke.py --run --output",
        "run_krew_smoke.py --run --output",
        "run_admission_kind_smoke.py --run --output",
        "capture_controller_resource_budget.py --output <kubectl-top-output.txt> --run",
        "build_external_evidence.py --kind kubectl-explain",
        "build_external_evidence.py --kind controller-resource-budget",
        "build_external_evidence.py --kind controller-live-loop",
        "check_live_evidence_coverage.py <manifest.json>",
        "build_release_evidence_directory.py <evidence-dir>",
    ):
        if snippet not in commands and snippet not in "\n".join(plan.get("closureCommands", [])):
            errors.append(f"external gate plan missing command: {snippet}")

    taskboard = TASKBOARD.read_text()
    if "doing: 0" not in subprocess.run(
        [sys.executable, "-B", "scripts/verify_release_taskboard.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    ).stdout:
        errors.append("taskboard verifier must report doing: 0")
    for snippet in ("generate_external_gate_plan.py", "verify_external_gate_plan.py"):
        if snippet not in README.read_text():
            errors.append(f"README missing external gate tool: {snippet}")
        if snippet not in LIVE_VALIDATION.read_text():
            errors.append(f"live validation doc missing external gate tool: {snippet}")
    if "External gate plan" not in taskboard:
        errors.append("taskboard missing external gate plan baseline row")

    if errors:
        print("external-gate-plan: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("external-gate-plan: passed")
    print("external-gates: 16")
    print("blocked-gates: 16")
    print("doing: 0")
    print("todo: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
