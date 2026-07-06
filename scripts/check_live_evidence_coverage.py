#!/usr/bin/env python3
"""Check whether a live evidence manifest covers release gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "kube-actuary.live-evidence-manifest.v1"
LIGHTWEIGHT_PROVIDERS = {"kind", "minikube", "microk8s", "k3s"}
MANAGED_PROVIDERS = {"eks", "gke", "aks"}
SINGLE_REPORT_GATES = {
    "helm-smoke",
    "krew-smoke",
    "admission-kind-smoke",
}


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("manifest root must be an object")
    return payload


def is_passing_run(report: dict[str, Any]) -> bool:
    summary = report.get("summary")
    return (
        report.get("mode") == "run"
        and isinstance(summary, dict)
        and summary.get("failed") == 0
        and isinstance(report.get("sha256"), str)
        and len(report["sha256"]) == 64
    )


def passing_reports(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    reports = manifest.get("reports")
    if not isinstance(reports, list):
        return []
    return [report for report in reports if isinstance(report, dict) and is_passing_run(report)]


def check_coverage(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schemaVersion") != MANIFEST_SCHEMA:
        errors.append(f"unsupported manifest schemaVersion: {manifest.get('schemaVersion')!r}")
        return errors

    reports = passing_reports(manifest)
    lightweight = {
        str(report.get("provider"))
        for report in reports
        if report.get("gate") == "lightweight-cluster-smoke"
    }
    managed = {
        str(report.get("provider"))
        for report in reports
        if report.get("gate") == "managed-kubernetes-smoke"
    }
    for provider in sorted(LIGHTWEIGHT_PROVIDERS - lightweight):
        errors.append(f"missing lightweight provider: {provider}")
    for provider in sorted(managed - MANAGED_PROVIDERS):
        errors.append(f"unexpected managed provider: {provider}")
    for provider in sorted(MANAGED_PROVIDERS - managed):
        errors.append(f"missing managed provider: {provider}")

    for gate in sorted(SINGLE_REPORT_GATES):
        if not any(report.get("gate") == gate for report in reports):
            errors.append(f"missing passing run report for gate: {gate}")

    summary = manifest.get("summary")
    if isinstance(summary, dict) and summary.get("failedReports", 0) != 0:
        errors.append("manifest contains failed reports")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check KubeActuary live evidence gate coverage.")
    parser.add_argument("manifest", help="live evidence manifest JSON")
    args = parser.parse_args(argv)

    try:
        errors = check_coverage(load_manifest(Path(args.manifest)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]

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
