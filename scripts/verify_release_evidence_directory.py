#!/usr/bin/env python3
"""Verify release evidence directory artifact generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY_BUILDER = ROOT / "scripts" / "build_release_evidence_directory.py"
EVIDENCE_BUILDER = ROOT / "scripts" / "build_external_evidence.py"
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


def evidence_matrix(evidence_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for provider in LIGHTWEIGHT_PROVIDERS:
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = provider
        path = evidence_dir / f"lightweight-{provider}.json"
        write_payload(path, payload)
        paths.append(path)
    for provider in MANAGED_PROVIDERS:
        payload = sample("kube-actuary.managed-kubernetes-smoke.v1")
        payload["provider"] = provider
        path = evidence_dir / f"managed-{provider}.json"
        write_payload(path, payload)
        paths.append(path)
    for index, schema in enumerate(SINGLE_REPORT_SCHEMAS):
        path = evidence_dir / f"single-{index}.json"
        write_payload(path, sample(schema))
        paths.append(path)
    return paths


def build_supplemental(evidence_dir: Path, kind: str, source: Path) -> Path:
    output = evidence_dir / f"{kind}.json"
    result = run_script(EVIDENCE_BUILDER, "--kind", kind, "--source", str(source), "--output", str(output))
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip())
    return output


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        evidence_dir.mkdir()
        evidence_matrix(evidence_dir)

        explain = tmpdir / "explain.txt"
        explain.write_text("KIND: OperationCapsule\nFIELDS:\n  spec\n  status\n")
        budget = tmpdir / "kubectl-top.txt"
        budget.write_text("POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n")
        loop = tmpdir / "loop.json"
        loop.write_text(json.dumps({"mode": "server-dry-run-loop", "writeExecution": "disabled", "readExecution": "kubectl-get", "failed": 0}))

        try:
            build_supplemental(evidence_dir, "kubectl-explain", explain)
            build_supplemental(evidence_dir, "controller-resource-budget", budget)
            build_supplemental(evidence_dir, "controller-live-loop", loop)
        except RuntimeError as exc:
            errors.append(f"supplemental evidence build failed: {exc}")

        first = run_script(DIRECTORY_BUILDER, str(evidence_dir))
        second = run_script(DIRECTORY_BUILDER, str(evidence_dir))
        write_payload(
            evidence_dir / ".kubeactuary" / "release-evidence-status.json",
            {"schemaVersion": "kube-actuary.release-evidence-status.v1"},
        )
        custom_output = tmpdir / "custom-output"
        custom = run_script(DIRECTORY_BUILDER, str(evidence_dir), "--output-dir", str(custom_output))
        manifest_path = evidence_dir / ".kubeactuary" / "live-evidence-manifest.json"
        bundle_path = evidence_dir / ".kubeactuary" / "external-evidence-bundle.json"
        custom_manifest_path = custom_output / "live-evidence-manifest.json"
        custom_manifest_written = custom_manifest_path.is_file()

        bad_dir = tmpdir / "bad-evidence"
        bad_dir.mkdir()
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = "kind"
        write_payload(bad_dir / "kind.json", payload)
        write_payload(
            bad_dir / "bad-supplemental.json",
            {"schemaVersion": "kube-actuary.external-evidence.v1", "kind": "kubectl-explain", "ok": False},
        )
        invalid = run_script(DIRECTORY_BUILDER, str(bad_dir))

        manifest_payload = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
        bundle_payload = json.loads(bundle_path.read_text()) if bundle_path.is_file() else {}

    for name, result in (("first", first), ("second", second)):
        if result.returncode != 0:
            errors.append(f"{name} directory build failed: {result.stderr.strip() or result.stdout.strip()}")
    if "live-reports: 10" not in second.stdout:
        errors.append("directory builder must ignore generated output artifacts on rerun")
    if custom.returncode != 0:
        errors.append(f"custom output-dir build failed: {custom.stderr.strip() or custom.stdout.strip()}")
    if "live-reports: 10" not in custom.stdout:
        errors.append("custom output-dir build must ignore default .kubeactuary metadata")
    if not custom_manifest_written:
        errors.append("custom output-dir build must write a manifest")
    if invalid.returncode == 0 or "supplemental evidence must be ok=true" not in invalid.stdout:
        errors.append("directory builder must reject failed supplemental evidence")
    if manifest_payload.get("schemaVersion") != "kube-actuary.live-evidence-manifest.v1":
        errors.append("directory builder must write a live evidence manifest")
    if manifest_payload.get("summary", {}).get("reports") != 10:
        errors.append("manifest must include ten live reports")
    if bundle_payload.get("schemaVersion") != "kube-actuary.external-evidence-bundle.v1":
        errors.append("directory builder must write an external evidence bundle")
    if bundle_payload.get("closure", {}).get("status") != "complete":
        errors.append("directory bundle must close all external gates")
    if bundle_payload.get("closure", {}).get("covered") != 16:
        errors.append("directory bundle must cover all VERIFY gates")
    if len(str(bundle_payload.get("manifest", {}).get("sha256", ""))) != 64:
        errors.append("bundle must record manifest sha256")
    if len(bundle_payload.get("supplementalEvidence", [])) != 3:
        errors.append("bundle must include three supplemental records")

    for snippet in ("build_release_evidence_directory.py", "verify_release_evidence_directory.py"):
        if snippet not in README.read_text():
            errors.append(f"README missing release evidence directory detail: {snippet}")
    for snippet in ("build_release_evidence_directory.py", "release-evidence-directory: passed"):
        if snippet not in LIVE_VALIDATION.read_text():
            errors.append(f"live validation doc missing release evidence directory detail: {snippet}")

    if errors:
        print("release-evidence-directory: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("release-evidence-directory: passed")
    print("live-reports: 10")
    print("supplemental: 3")
    print("closure: complete")
    print("metadata: ignored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
