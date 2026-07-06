#!/usr/bin/env python3
"""Verify the live evidence report validator and documentation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_live_evidence.py"
DOC = ROOT / "docs" / "live-validation.md"
SCHEMAS = (
    "kube-actuary.lightweight-smoke.v1",
    "kube-actuary.helm-smoke.v1",
    "kube-actuary.krew-smoke.v1",
    "kube-actuary.admission-kind-smoke.v1",
    "kube-actuary.managed-kubernetes-smoke.v1",
)


def base(schema: str) -> dict[str, Any]:
    return {
        "schemaVersion": schema,
        "mode": "run",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "commands": [
            {
                "command": ["example", "check"],
                "exitCode": 0,
                "ok": True,
                "stdout": "ok\n",
                "stderr": "",
            }
        ],
        "summary": {"total": 1, "passed": 1, "failed": 0},
    }


def sample(schema: str) -> dict[str, Any]:
    payload = base(schema)
    if schema == "kube-actuary.lightweight-smoke.v1":
        payload.update({"provider": "kind", "namespace": "kubeactuary-system", "clusterWrites": "server-side-dry-run-only"})
    elif schema == "kube-actuary.helm-smoke.v1":
        payload.update({"release": "kubeactuary", "namespace": "kubeactuary-system", "chart": "charts/kubeactuary", "clusterWrites": "dry-run-only"})
    elif schema == "kube-actuary.krew-smoke.v1":
        payload.update({"manifest": "dist/actuary.yaml", "clusterAccess": "none", "filesystemWrites": "isolated-krew-root", "network": "depends-on-manifest-uri"})
    elif schema == "kube-actuary.admission-kind-smoke.v1":
        payload.update({"clusterWrites": "server-side-dry-run-only", "localServer": "loopback-only"})
    elif schema == "kube-actuary.managed-kubernetes-smoke.v1":
        payload.update({"provider": "eks", "namespace": "kubeactuary-system", "clusterAccess": "current-context", "clusterWrites": "server-side-dry-run-only", "cloudApi": "version-command-only"})
    return payload


def run_validator(*paths: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(VALIDATOR), *(str(path) for path in paths)],
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
        valid = run_validator(*paths)

        bad = tmpdir / "bad.json"
        bad.write_text(json.dumps({"schemaVersion": "unknown.v1", "commands": [], "summary": {}}))
        invalid = run_validator(bad)

    if valid.returncode != 0:
        errors.append(f"valid evidence reports failed: {valid.stderr.strip() or valid.stdout.strip()}")
    if "live-evidence: passed" not in valid.stdout or "files: 5" not in valid.stdout:
        errors.append("validator must pass five supported schema samples")
    if invalid.returncode == 0:
        errors.append("validator must reject unsupported schema")
    if "unsupported schemaVersion" not in invalid.stdout:
        errors.append("invalid schema output must explain unsupported schemaVersion")

    doc = DOC.read_text()
    for snippet in (
        "validate_live_evidence.py",
        "kube-actuary.lightweight-smoke.v1",
        "kube-actuary.helm-smoke.v1",
        "kube-actuary.krew-smoke.v1",
        "kube-actuary.admission-kind-smoke.v1",
        "kube-actuary.managed-kubernetes-smoke.v1",
    ):
        if snippet not in doc:
            errors.append(f"live validation doc missing: {snippet}")

    if errors:
        print("live-evidence-schema: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("live-evidence-schema: passed")
    print("schemas: 5")
    print("validator: validate_live_evidence.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
