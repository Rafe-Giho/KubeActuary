#!/usr/bin/env python3
"""Build a manifest for captured live evidence reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_live_evidence import validate_file  # noqa: E402


MANIFEST_SCHEMA = "kube-actuary.live-evidence-manifest.v1"
SCHEMA_GATES = {
    "kube-actuary.lightweight-smoke.v1": "lightweight-cluster-smoke",
    "kube-actuary.helm-smoke.v1": "helm-smoke",
    "kube-actuary.krew-smoke.v1": "krew-smoke",
    "kube-actuary.admission-kind-smoke.v1": "admission-kind-smoke",
    "kube-actuary.managed-kubernetes-smoke.v1": "managed-kubernetes-smoke",
}
GATE_ORDER = tuple(SCHEMA_GATES.values())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return payload


def report_entry(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    schema = str(payload.get("schemaVersion"))
    entry: dict[str, Any] = {
        "path": str(path),
        "sha256": sha256(path),
        "schemaVersion": schema,
        "gate": SCHEMA_GATES[schema],
        "capturedAt": payload.get("capturedAt"),
        "mode": payload.get("mode"),
        "summary": payload.get("summary"),
    }
    for optional in ("provider", "namespace", "release", "chart", "manifest"):
        if optional in payload:
            entry[optional] = payload[optional]
    return entry


def build_manifest(paths: list[Path]) -> dict[str, Any]:
    reports = [report_entry(path, load_json(path)) for path in paths]
    gates = [gate for gate in GATE_ORDER if any(report["gate"] == gate for report in reports)]
    failed_reports = sum(
        1
        for report in reports
        if isinstance(report.get("summary"), dict) and report["summary"].get("failed", 0) > 0
    )
    return {
        "schemaVersion": MANIFEST_SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "reports": reports,
        "summary": {
            "reports": len(reports),
            "gates": gates,
            "failedReports": failed_reports,
        },
    }


def write_manifest(manifest: dict[str, Any], output: str) -> None:
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if output == "-":
        print(encoded, end="")
        return
    Path(output).write_text(encoded)
    print(f"live-evidence-manifest: wrote {output}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a KubeActuary live evidence manifest.")
    parser.add_argument("files", nargs="+", help="captured live evidence JSON files")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    paths = [Path(name) for name in args.files]
    errors: list[str] = []
    for path in paths:
        errors.extend(validate_file(path))
    if errors:
        print("live-evidence-manifest: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    try:
        write_manifest(build_manifest(paths), args.output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("live-evidence-manifest: failed")
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
