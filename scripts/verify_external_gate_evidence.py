#!/usr/bin/env python3
"""Verify external gate evidence evaluation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_live_evidence_manifest.py"
EVALUATOR = ROOT / "scripts" / "evaluate_external_gate_evidence.py"
README = ROOT / "README.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
sys.path.insert(0, str(ROOT))

from scripts.verify_live_evidence_schema import sample  # noqa: E402


LIGHTWEIGHT_PROVIDERS = ("kind", "minikube", "microk8s", "k3s")
MANAGED_PROVIDERS = ("eks", "gke", "aks")
SINGLE_REPORT_SCHEMAS = (
    "kube-actuary.helm-smoke.v1",
    "kube-actuary.krew-smoke.v1",
    "kube-actuary.admission-kind-smoke.v1",
)


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(script), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload))


def full_matrix(tmpdir: Path) -> list[Path]:
    paths: list[Path] = []
    for provider in LIGHTWEIGHT_PROVIDERS:
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = provider
        path = tmpdir / f"lightweight-{provider}.json"
        write_payload(path, payload)
        paths.append(path)
    for provider in MANAGED_PROVIDERS:
        payload = sample("kube-actuary.managed-kubernetes-smoke.v1")
        payload["provider"] = provider
        path = tmpdir / f"managed-{provider}.json"
        write_payload(path, payload)
        paths.append(path)
    for index, schema in enumerate(SINGLE_REPORT_SCHEMAS):
        path = tmpdir / f"single-{index}.json"
        write_payload(path, sample(schema))
        paths.append(path)
    return paths


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        manifest = tmpdir / "manifest.json"
        build = run_script(BUILDER, *(str(path) for path in full_matrix(tmpdir)), "--output", str(manifest))
        evaluation = run_script(EVALUATOR, str(manifest))

    if build.returncode != 0:
        errors.append(f"manifest build failed: {build.stderr.strip() or build.stdout.strip()}")
    if evaluation.returncode != 0:
        errors.append(f"evaluation failed: {evaluation.stderr.strip() or evaluation.stdout.strip()}")
        payload = {}
    else:
        try:
            payload = json.loads(evaluation.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"evaluation output must be JSON: {exc}")
            payload = {}

    summary = payload.get("summary", {})
    if payload.get("schemaVersion") != "kube-actuary.external-gate-evaluation.v1":
        errors.append("external gate evaluation schemaVersion mismatch")
    if summary.get("total") != 16:
        errors.append(f"expected 16 evaluated gates, got {summary.get('total')!r}")
    if summary.get("covered") != 12 or summary.get("uncovered") != 4:
        errors.append(f"expected 12 covered and 4 uncovered gates, got {summary!r}")

    gates = payload.get("gates", [])
    explain_gate = next((gate for gate in gates if "explain" in str(gate.get("item", "")).lower()), {})
    budget_gate = next((gate for gate in gates if gate.get("kind") == "controller-resource-budget"), {})
    if explain_gate.get("covered") is not False or "kubectl explain" not in explain_gate.get("reason", ""):
        errors.append("kubectl explain gate must stay uncovered by smoke manifest")
    if budget_gate.get("covered") is not False or "resource measurement" not in budget_gate.get("reason", ""):
        errors.append("resource budget gate must stay uncovered by smoke manifest")
    if not any(gate.get("kind") == "packaging" and gate.get("covered") is True for gate in gates):
        errors.append("packaging gate should be covered by helm and krew smoke reports")

    for snippet in ("evaluate_external_gate_evidence.py", "verify_external_gate_evidence.py"):
        if snippet not in README.read_text():
            errors.append(f"README missing external gate evidence tool: {snippet}")
        if snippet not in LIVE_VALIDATION.read_text():
            errors.append(f"live validation doc missing external gate evidence tool: {snippet}")

    if errors:
        print("external-gate-evidence: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("external-gate-evidence: passed")
    print("covered: 12")
    print("uncovered: 4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
