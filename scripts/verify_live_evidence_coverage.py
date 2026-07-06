#!/usr/bin/env python3
"""Verify live evidence coverage checks and documentation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_live_evidence_manifest.py"
CHECKER = ROOT / "scripts" / "check_live_evidence_coverage.py"
DOC = ROOT / "docs" / "live-validation.md"
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


def build_manifest(output: Path, evidence_paths: list[Path]) -> subprocess.CompletedProcess[str]:
    return run_script(BUILDER, *(str(path) for path in evidence_paths), "--output", str(output))


def write_full_matrix(tmpdir: Path) -> list[Path]:
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


def write_partial_matrix(tmpdir: Path) -> list[Path]:
    paths: list[Path] = []
    for schema in (
        "kube-actuary.lightweight-smoke.v1",
        "kube-actuary.managed-kubernetes-smoke.v1",
        "kube-actuary.helm-smoke.v1",
    ):
        path = tmpdir / f"partial-{len(paths)}.json"
        write_payload(path, sample(schema))
        paths.append(path)
    return paths


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        full_manifest = tmpdir / "full-manifest.json"
        full_build = build_manifest(full_manifest, write_full_matrix(tmpdir))
        full_check = run_script(CHECKER, str(full_manifest))

        partial_manifest = tmpdir / "partial-manifest.json"
        partial_build = build_manifest(partial_manifest, write_partial_matrix(tmpdir))
        partial_check = run_script(CHECKER, str(partial_manifest))

    if full_build.returncode != 0:
        errors.append(f"full manifest build failed: {full_build.stderr.strip() or full_build.stdout.strip()}")
    if full_check.returncode != 0:
        errors.append(f"full coverage check failed: {full_check.stderr.strip() or full_check.stdout.strip()}")
    if "live-evidence-coverage: passed" not in full_check.stdout:
        errors.append("full coverage check must pass")
    if "required-providers: 7" not in full_check.stdout:
        errors.append("full coverage check must report seven required providers")

    if partial_build.returncode != 0:
        errors.append(f"partial manifest build failed: {partial_build.stderr.strip() or partial_build.stdout.strip()}")
    if partial_check.returncode == 0:
        errors.append("partial coverage check must fail")
    if "missing lightweight provider: minikube" not in partial_check.stdout:
        errors.append("partial coverage must name missing lightweight providers")
    if "missing managed provider: aks" not in partial_check.stdout:
        errors.append("partial coverage must name missing managed providers")
    if "missing passing run report for gate: admission-kind-smoke" not in partial_check.stdout:
        errors.append("partial coverage must name missing single-report gates")

    doc = DOC.read_text()
    for snippet in (
        "check_live_evidence_coverage.py",
        "verify_live_evidence_coverage.py",
        "kind, minikube",
        "MicroK8s, and k3s",
        "EKS, GKE, and AKS",
        "required-providers: 7",
    ):
        if snippet not in doc:
            errors.append(f"live validation doc missing: {snippet}")

    if errors:
        print("live-evidence-coverage: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("live-evidence-coverage: passed")
    print("required-gates: 5")
    print("required-providers: 7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
