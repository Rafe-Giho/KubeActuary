#!/usr/bin/env python3
"""Verify release evidence directory status inspection."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "scripts" / "inspect_release_evidence_directory.py"
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


def write_full_matrix(evidence_dir: Path) -> None:
    for provider in LIGHTWEIGHT_PROVIDERS:
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = provider
        write_payload(evidence_dir / f"lightweight-{provider}.json", payload)
    for provider in MANAGED_PROVIDERS:
        payload = sample("kube-actuary.managed-kubernetes-smoke.v1")
        payload["provider"] = provider
        write_payload(evidence_dir / f"managed-{provider}.json", payload)
    for index, schema in enumerate(SINGLE_REPORT_SCHEMAS):
        write_payload(evidence_dir / f"single-{index}.json", sample(schema))


def build_supplemental(evidence_dir: Path, kind: str, source: Path) -> None:
    output = evidence_dir / f"{kind}.json"
    result = run_script(EVIDENCE_BUILDER, "--kind", kind, "--source", str(source), "--output", str(output))
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip())


def write_supplemental(evidence_dir: Path, tmpdir: Path) -> None:
    explain = tmpdir / "explain.txt"
    explain.write_text("KIND: OperationCapsule\nFIELDS:\n  spec\n  status\n")
    budget = tmpdir / "kubectl-top.txt"
    budget.write_text("POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n")
    loop = tmpdir / "loop.json"
    loop.write_text(json.dumps({"mode": "server-dry-run-loop", "writeExecution": "disabled", "readExecution": "kubectl-get", "failed": 0}))
    build_supplemental(evidence_dir, "kubectl-explain", explain)
    build_supplemental(evidence_dir, "controller-resource-budget", budget)
    build_supplemental(evidence_dir, "controller-live-loop", loop)


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        partial_dir = tmpdir / "partial"
        partial_dir.mkdir()
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = "kind"
        write_payload(partial_dir / "kind.json", payload)
        partial = run_script(INSPECTOR, str(partial_dir), "--format", "json")

        full_dir = tmpdir / "full"
        full_dir.mkdir()
        write_full_matrix(full_dir)
        try:
            write_supplemental(full_dir, tmpdir)
        except RuntimeError as exc:
            errors.append(f"supplemental evidence build failed: {exc}")
        complete = run_script(INSPECTOR, str(full_dir), "--format", "json")
        text = run_script(INSPECTOR, str(full_dir))

        output = tmpdir / "status.json"
        written = run_script(INSPECTOR, str(full_dir), "--format", "json", "--output", str(output))
        output_written = output.is_file()

        invalid_dir = tmpdir / "invalid"
        invalid_dir.mkdir()
        write_payload(invalid_dir / "bad.json", {"schemaVersion": "kube-actuary.external-evidence.v1", "kind": "kubectl-explain", "ok": False})
        invalid = run_script(INSPECTOR, str(invalid_dir))

    if partial.returncode != 0:
        errors.append(f"partial status failed: {partial.stderr.strip() or partial.stdout.strip()}")
        partial_payload = {}
    else:
        partial_payload = json.loads(partial.stdout)
    if complete.returncode != 0:
        errors.append(f"complete status failed: {complete.stderr.strip() or complete.stdout.strip()}")
        complete_payload = {}
    else:
        complete_payload = json.loads(complete.stdout)
    if text.returncode != 0 or "release-evidence-status: complete" not in text.stdout:
        errors.append("text status output must report complete status")
    if written.returncode != 0 or not output_written:
        errors.append("status inspector must write requested output file")
    if invalid.returncode == 0 or "supplemental evidence must be ok=true" not in invalid.stdout:
        errors.append("status inspector must reject invalid supplemental evidence")

    if partial_payload.get("schemaVersion") != "kube-actuary.release-evidence-status.v1":
        errors.append("status schemaVersion mismatch")
    if partial_payload.get("summary", {}).get("status") != "partial":
        errors.append("partial evidence directory must report partial")
    if partial_payload.get("summary", {}).get("liveReports") != 1:
        errors.append("partial evidence directory must count one live report")
    if not partial_payload.get("missing", {}).get("coverage"):
        errors.append("partial status must include coverage misses")
    if not any("run_managed_kubernetes_smoke.py" in command for command in partial_payload.get("nextCommands", [])):
        errors.append("partial status must include next provider commands")

    if complete_payload.get("summary", {}).get("status") != "complete":
        errors.append("full evidence directory must report complete")
    if complete_payload.get("summary", {}).get("liveReports") != 10:
        errors.append("full evidence directory must count ten live reports")
    if complete_payload.get("summary", {}).get("supplementalEvidence") != 3:
        errors.append("full evidence directory must count three supplemental records")
    if complete_payload.get("summary", {}).get("coveredGates") != 16:
        errors.append("full evidence directory must cover all external gates")
    if complete_payload.get("summary", {}).get("coverageErrors") != 0:
        errors.append("full evidence directory must have no coverage errors")

    for snippet in ("inspect_release_evidence_directory.py", "kube-actuary.release-evidence-status.v1"):
        if snippet not in README.read_text():
            errors.append(f"README missing release evidence status detail: {snippet}")
        if snippet not in LIVE_VALIDATION.read_text():
            errors.append(f"live validation doc missing release evidence status detail: {snippet}")

    if errors:
        print("release-evidence-status: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("release-evidence-status: passed")
    print("partial: ok")
    print("complete: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
