#!/usr/bin/env python3
"""Evaluate external taskboard gates against a live evidence manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_live_evidence_coverage import (  # noqa: E402
    LIGHTWEIGHT_PROVIDERS,
    MANAGED_PROVIDERS,
    load_manifest,
    passing_reports,
)
from scripts.generate_external_gate_plan import build_plan  # noqa: E402


SCHEMA_VERSION = "kube-actuary.external-gate-evaluation.v1"
SUPPLEMENTAL_SCHEMA = "kube-actuary.external-evidence.v1"
SUPPLEMENTAL_KINDS = {
    "kubectl-explain",
    "controller-resource-budget",
    "controller-live-loop",
}


def evidence_state(manifest: dict[str, Any]) -> dict[str, Any]:
    reports = passing_reports(manifest)
    return {
        "lightweightProviders": {
            str(report.get("provider"))
            for report in reports
            if report.get("gate") == "lightweight-cluster-smoke"
        },
        "managedProviders": {
            str(report.get("provider"))
            for report in reports
            if report.get("gate") == "managed-kubernetes-smoke"
        },
        "gates": {str(report.get("gate")) for report in reports},
    }


def load_supplemental(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: supplemental evidence root must be an object")
    if payload.get("schemaVersion") != SUPPLEMENTAL_SCHEMA:
        raise ValueError(f"{path}: unsupported supplemental evidence schemaVersion: {payload.get('schemaVersion')!r}")
    if payload.get("kind") not in SUPPLEMENTAL_KINDS:
        raise ValueError(f"{path}: unsupported supplemental evidence kind: {payload.get('kind')!r}")
    if payload.get("ok") is not True:
        raise ValueError(f"{path}: supplemental evidence must be ok=true")
    return payload


def supplemental_state(paths: list[Path]) -> dict[str, Any]:
    records = [load_supplemental(path) for path in paths]
    return {
        "kinds": {record["kind"] for record in records},
        "records": records,
    }


def gate_status(gate: dict[str, Any], state: dict[str, Any], supplemental: dict[str, Any]) -> tuple[bool, str]:
    kind = gate.get("kind")
    item = str(gate.get("item", "")).lower()
    if kind == "lightweight-cluster":
        missing = sorted(LIGHTWEIGHT_PROVIDERS - state["lightweightProviders"])
        return (not missing, "all lightweight providers present" if not missing else f"missing lightweight providers: {', '.join(missing)}")
    if kind == "managed-kubernetes":
        missing = sorted(MANAGED_PROVIDERS - state["managedProviders"])
        return (not missing, "all managed providers present" if not missing else f"missing managed providers: {', '.join(missing)}")
    if kind == "helm":
        covered = "helm-smoke" in state["gates"]
        return (covered, "helm smoke present" if covered else "missing helm smoke report")
    if kind == "krew":
        covered = "krew-smoke" in state["gates"]
        return (covered, "krew smoke present" if covered else "missing krew smoke report")
    if kind == "admission":
        covered = "admission-kind-smoke" in state["gates"]
        return (covered, "admission smoke present" if covered else "missing admission smoke report")
    if kind == "packaging":
        missing = sorted({"helm-smoke", "krew-smoke"} - state["gates"])
        return (not missing, "helm and krew smoke present" if not missing else f"missing packaging reports: {', '.join(missing)}")
    if kind == "crd" and "explain" not in item:
        missing = sorted(LIGHTWEIGHT_PROVIDERS - state["lightweightProviders"])
        return (not missing, "CRD smoke covered by lightweight matrix" if not missing else f"missing CRD smoke providers: {', '.join(missing)}")
    if kind == "crd":
        covered = "kubectl-explain" in supplemental["kinds"]
        return (covered, "kubectl explain supplemental evidence present" if covered else "kubectl explain live output is not represented by smoke evidence manifest")
    if kind == "controller-resource-budget":
        covered = "controller-resource-budget" in supplemental["kinds"]
        return (covered, "controller resource measurement evidence present" if covered else "controller resource measurement evidence is not represented by smoke evidence manifest")
    if kind == "controller":
        missing = sorted({"controller-live-loop", "controller-resource-budget"} - supplemental["kinds"])
        return (not missing, "controller live loop and resource evidence present" if not missing else f"missing controller supplemental evidence: {', '.join(missing)}")
    return (False, "no manifest coverage rule for this gate")


def evaluate(manifest: dict[str, Any], supplemental_paths: list[Path] | None = None) -> dict[str, Any]:
    plan = build_plan()
    state = evidence_state(manifest)
    supplemental = supplemental_state(supplemental_paths or [])
    evaluated = []
    for gate in plan["gates"]:
        covered, reason = gate_status(gate, state, supplemental)
        evaluated.append({**gate, "covered": covered, "reason": reason})
    covered_count = sum(1 for gate in evaluated if gate["covered"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "planSchemaVersion": plan["schemaVersion"],
        "manifestSchemaVersion": manifest.get("schemaVersion"),
        "supplementalEvidence": sorted(supplemental["kinds"]),
        "summary": {
            "total": len(evaluated),
            "covered": covered_count,
            "uncovered": len(evaluated) - covered_count,
        },
        "gates": evaluated,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate external gates against a live evidence manifest.")
    parser.add_argument("manifest", help="live evidence manifest JSON")
    parser.add_argument("--evidence", action="append", default=[], help="supplemental external evidence JSON")
    args = parser.parse_args(argv)

    try:
        result = evaluate(load_manifest(Path(args.manifest)), [Path(path) for path in args.evidence])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("external-gate-evidence: failed")
        print(f"error: {exc}")
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
