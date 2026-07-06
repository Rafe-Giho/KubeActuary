#!/usr/bin/env python3
"""Verify external evidence bundle generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_BUILDER = ROOT / "scripts" / "build_live_evidence_manifest.py"
EVIDENCE_BUILDER = ROOT / "scripts" / "build_external_evidence.py"
BUNDLE_BUILDER = ROOT / "scripts" / "build_external_evidence_bundle.py"
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


def evidence_matrix(tmpdir: Path) -> list[Path]:
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


def build_supplemental(tmpdir: Path, kind: str, source: Path) -> Path:
    output = tmpdir / f"{kind}.json"
    result = run_script(EVIDENCE_BUILDER, "--kind", kind, "--source", str(source), "--output", str(output))
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip())
    return output


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        manifest = tmpdir / "manifest.json"
        manifest_result = run_script(MANIFEST_BUILDER, *(str(path) for path in evidence_matrix(tmpdir)), "--output", str(manifest))

        explain = tmpdir / "explain.txt"
        explain.write_text("KIND: OperationCapsule\nFIELDS:\n  spec\n  status\n")
        budget = tmpdir / "kubectl-top.txt"
        budget.write_text("POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n")
        loop = tmpdir / "loop.json"
        loop.write_text(json.dumps({"mode": "server-dry-run-loop", "writeExecution": "disabled", "readExecution": "kubectl-get", "failed": 0}))

        try:
            supplemental = [
                build_supplemental(tmpdir, "kubectl-explain", explain),
                build_supplemental(tmpdir, "controller-resource-budget", budget),
                build_supplemental(tmpdir, "controller-live-loop", loop),
            ]
        except RuntimeError as exc:
            errors.append(f"supplemental evidence build failed: {exc}")
            supplemental = []

        smoke_only = run_script(BUNDLE_BUILDER, str(manifest))
        full = run_script(BUNDLE_BUILDER, str(manifest), *(arg for path in supplemental for arg in ("--evidence", str(path))))
        output = tmpdir / "bundle.json"
        written = run_script(BUNDLE_BUILDER, str(manifest), *(arg for path in supplemental for arg in ("--evidence", str(path))), "--output", str(output))
        output_written = output.is_file()

        bad = tmpdir / "bad-evidence.json"
        bad.write_text(json.dumps({"schemaVersion": "kube-actuary.external-evidence.v1", "kind": "kubectl-explain", "ok": False}))
        invalid = run_script(BUNDLE_BUILDER, str(manifest), "--evidence", str(bad))

    if manifest_result.returncode != 0:
        errors.append(f"manifest build failed: {manifest_result.stdout.strip() or manifest_result.stderr.strip()}")
    for name, result in (("smoke-only", smoke_only), ("full", full)):
        if result.returncode != 0:
            errors.append(f"{name} bundle failed: {result.stderr.strip() or result.stdout.strip()}")
    if written.returncode != 0 or not output_written:
        errors.append("bundle builder must write requested output file")
    if invalid.returncode == 0 or "supplemental evidence must be ok=true" not in invalid.stdout:
        errors.append("bundle builder must reject failed supplemental evidence")

    try:
        smoke_payload = json.loads(smoke_only.stdout)
        full_payload = json.loads(full.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"bundle output must be JSON: {exc}")
        smoke_payload = {}
        full_payload = {}

    if smoke_payload.get("schemaVersion") != "kube-actuary.external-evidence-bundle.v1":
        errors.append("bundle schemaVersion mismatch")
    if smoke_payload.get("closure", {}).get("status") != "partial":
        errors.append("smoke-only bundle must be partial")
    if full_payload.get("closure", {}).get("status") != "complete":
        errors.append("full bundle must be complete")
    if full_payload.get("closure", {}).get("covered") != 16 or full_payload.get("closure", {}).get("uncovered") != 0:
        errors.append("full bundle must close all VERIFY gates")
    if len(full_payload.get("supplementalEvidence", [])) != 3:
        errors.append("full bundle must include three supplemental evidence records")
    for record in [full_payload.get("manifest", {}), *full_payload.get("supplementalEvidence", [])]:
        if len(str(record.get("sha256", ""))) != 64:
            errors.append("bundle inputs must record sha256 digests")

    for snippet in ("build_external_evidence_bundle.py", "kube-actuary.external-evidence-bundle.v1"):
        if snippet not in README.read_text():
            errors.append(f"README missing external evidence bundle detail: {snippet}")
        if snippet not in LIVE_VALIDATION.read_text():
            errors.append(f"live validation doc missing external evidence bundle detail: {snippet}")

    if errors:
        print("external-evidence-bundle: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("external-evidence-bundle: passed")
    print("closure: complete")
    print("supplemental: 3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
