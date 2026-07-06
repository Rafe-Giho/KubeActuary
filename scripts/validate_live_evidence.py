#!/usr/bin/env python3
"""Validate captured live evidence report JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SUPPORTED_SCHEMAS = {
    "kube-actuary.lightweight-smoke.v1",
    "kube-actuary.helm-smoke.v1",
    "kube-actuary.krew-smoke.v1",
    "kube-actuary.admission-kind-smoke.v1",
    "kube-actuary.managed-kubernetes-smoke.v1",
}
PROVIDERS = {"eks", "gke", "aks"}


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_common(path: Path, payload: dict[str, Any], errors: list[str]) -> str:
    schema = payload.get("schemaVersion")
    require(schema in SUPPORTED_SCHEMAS, f"{path}: unsupported schemaVersion: {schema!r}", errors)
    require(isinstance(payload.get("capturedAt"), str) and payload["capturedAt"], f"{path}: capturedAt is required", errors)
    commands = payload.get("commands")
    require(isinstance(commands, list) and commands, f"{path}: commands must be a non-empty list", errors)
    summary = payload.get("summary")
    require(isinstance(summary, dict), f"{path}: summary object is required", errors)
    if isinstance(summary, dict) and isinstance(commands, list):
        require(summary.get("total") == len(commands), f"{path}: summary.total must equal command count", errors)
        failed = sum(1 for record in commands if isinstance(record, dict) and record.get("ok") is False)
        require(summary.get("failed") == failed, f"{path}: summary.failed must match command records", errors)
        require(summary.get("passed") == len(commands) - failed, f"{path}: summary.passed must match command records", errors)
    for index, record in enumerate(commands if isinstance(commands, list) else []):
        if not isinstance(record, dict):
            errors.append(f"{path}: command record {index} must be an object")
            continue
        require(isinstance(record.get("command"), list) and record["command"], f"{path}: command record {index} missing command list", errors)
        if "ok" in record:
            require(isinstance(record.get("ok"), bool), f"{path}: command record {index} ok must be boolean", errors)
        if "exitCode" in record:
            require(isinstance(record.get("exitCode"), int), f"{path}: command record {index} exitCode must be integer", errors)
        if "stdout" in record or "stderr" in record:
            require(isinstance(record.get("stdout", ""), str), f"{path}: command record {index} stdout must be string", errors)
            require(isinstance(record.get("stderr", ""), str), f"{path}: command record {index} stderr must be string", errors)
    return str(schema)


def validate_schema(path: Path, payload: dict[str, Any], schema: str, errors: list[str]) -> None:
    if schema == "kube-actuary.lightweight-smoke.v1":
        require(payload.get("provider") in {"kind", "minikube", "microk8s", "k3s"}, f"{path}: invalid lightweight provider", errors)
        require(payload.get("clusterWrites") == "server-side-dry-run-only", f"{path}: lightweight smoke writes must be dry-run only", errors)
    elif schema == "kube-actuary.helm-smoke.v1":
        require(payload.get("chart") == "charts/kubeactuary", f"{path}: Helm chart path mismatch", errors)
        require(payload.get("clusterWrites") == "dry-run-only", f"{path}: Helm smoke writes must be dry-run only", errors)
    elif schema == "kube-actuary.krew-smoke.v1":
        require(payload.get("clusterAccess") == "none", f"{path}: Krew smoke must not require cluster access", errors)
        require(payload.get("filesystemWrites") == "isolated-krew-root", f"{path}: Krew smoke must isolate filesystem writes", errors)
    elif schema == "kube-actuary.admission-kind-smoke.v1":
        require(payload.get("clusterWrites") == "server-side-dry-run-only", f"{path}: admission smoke writes must be dry-run only", errors)
        require(payload.get("localServer") == "loopback-only", f"{path}: admission smoke server must be loopback-only", errors)
    elif schema == "kube-actuary.managed-kubernetes-smoke.v1":
        require(payload.get("provider") in PROVIDERS, f"{path}: invalid managed provider", errors)
        require(payload.get("clusterAccess") == "current-context", f"{path}: managed smoke must use current context", errors)
        require(payload.get("clusterWrites") == "server-side-dry-run-only", f"{path}: managed smoke writes must be dry-run only", errors)
        require(payload.get("cloudApi") == "version-command-only", f"{path}: managed smoke cloud API use must be version-only", errors)


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError:
        return [f"{path}: file not found"]
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]
    if not isinstance(payload, dict):
        return [f"{path}: JSON root must be an object"]
    schema = validate_common(path, payload, errors)
    validate_schema(path, payload, schema, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate captured KubeActuary live evidence JSON.")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)

    errors: list[str] = []
    for name in args.files:
        errors.extend(validate_file(Path(name)))
    if errors:
        print("live-evidence: failed")
        for error in errors:
            print(f"error: {error}")
        return 1
    print("live-evidence: passed")
    print(f"files: {len(args.files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
