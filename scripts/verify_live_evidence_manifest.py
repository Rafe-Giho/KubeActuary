#!/usr/bin/env python3
"""Verify live evidence manifest generation and docs."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_live_evidence_manifest.py"
DOC = ROOT / "docs" / "live-validation.md"
sys.path.insert(0, str(ROOT))

from scripts.verify_live_evidence_schema import SCHEMAS, sample  # noqa: E402


EXPECTED_GATES = {
    "lightweight-cluster-smoke",
    "helm-smoke",
    "krew-smoke",
    "admission-kind-smoke",
    "managed-kubernetes-smoke",
}


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
        paths = []
        for index, schema in enumerate(SCHEMAS):
            path = tmpdir / f"evidence-{index}.json"
            path.write_text(json.dumps(sample(schema)))
            paths.append(path)

        valid = run_builder(*(str(path) for path in paths))
        if valid.returncode != 0:
            errors.append(f"valid manifest generation failed: {valid.stderr.strip() or valid.stdout.strip()}")
            manifest = {}
        else:
            try:
                manifest = json.loads(valid.stdout)
            except json.JSONDecodeError as exc:
                errors.append(f"manifest output must be JSON: {exc}")
                manifest = {}

        output = tmpdir / "manifest.json"
        written = run_builder(*(str(path) for path in paths), "--output", str(output))
        if written.returncode != 0:
            errors.append(f"output-file manifest generation failed: {written.stderr.strip() or written.stdout.strip()}")
        elif not output.is_file():
            errors.append("manifest builder must write the requested output file")

        bad = tmpdir / "bad.json"
        bad.write_text(json.dumps({"schemaVersion": "unknown.v1", "commands": [], "summary": {}}))
        invalid = run_builder(str(bad))

    if manifest.get("schemaVersion") != "kube-actuary.live-evidence-manifest.v1":
        errors.append("manifest schemaVersion mismatch")
    reports = manifest.get("reports", [])
    if not isinstance(reports, list) or len(reports) != 5:
        errors.append("manifest must include five evidence reports")
    gates = set(manifest.get("summary", {}).get("gates", []))
    if gates != EXPECTED_GATES:
        errors.append(f"manifest gates mismatch: {sorted(gates)}")
    if manifest.get("summary", {}).get("failedReports") != 0:
        errors.append("sample manifest should have zero failed reports")
    for report in reports if isinstance(reports, list) else []:
        if not isinstance(report, dict):
            errors.append("manifest report entries must be objects")
            continue
        for field in ("path", "sha256", "schemaVersion", "gate", "summary"):
            if field not in report:
                errors.append(f"manifest report missing field: {field}")
        if len(str(report.get("sha256", ""))) != 64:
            errors.append("manifest report sha256 must be a hex digest")

    if invalid.returncode == 0:
        errors.append("manifest builder must reject invalid evidence")
    if "live-evidence-manifest: failed" not in invalid.stdout:
        errors.append("invalid evidence output must use manifest failure prefix")
    if "unsupported schemaVersion" not in invalid.stdout:
        errors.append("invalid evidence output must include validator errors")

    doc = DOC.read_text()
    for snippet in (
        "build_live_evidence_manifest.py",
        "validate_live_evidence.py",
        "kube-actuary.live-evidence-manifest.v1",
        "lightweight-cluster-smoke",
        "managed-kubernetes-smoke",
    ):
        if snippet not in doc:
            errors.append(f"live validation doc missing: {snippet}")

    if errors:
        print("live-evidence-manifest: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("live-evidence-manifest: passed")
    print("reports: 5")
    print("gates: 5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
