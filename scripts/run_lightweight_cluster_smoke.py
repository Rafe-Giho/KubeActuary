#!/usr/bin/env python3
"""Run or print lightweight cluster smoke checks for KubeActuary."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("kind", "minikube", "microk8s", "k3s")
CRD = "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"
NAMESPACE_RBAC = "deploy/controller/namespace-scoped-rbac.yaml"
CLUSTER_RBAC = "deploy/controller/cluster-scoped-rbac.yaml"
CONTROLLER_SELECTOR = "app.kubernetes.io/name=kubeactuary,app.kubernetes.io/component=controller"


def smoke_commands(kubectl: str, namespace: str) -> list[list[str]]:
    prefix = shlex.split(kubectl)
    return [
        [*prefix, "version", "--client=true", "-o", "json"],
        [*prefix, "cluster-info"],
        [*prefix, "apply", "--dry-run=server", "-f", CRD],
        [*prefix, "apply", "--dry-run=server", "-f", NAMESPACE_RBAC],
        [*prefix, "apply", "--dry-run=server", "-f", CLUSTER_RBAC],
        [*prefix, "auth", "can-i", "get", "operationcapsules.ops.kubeactuary.dev", "--all-namespaces"],
        [*prefix, "auth", "can-i", "watch", "operationcapsules.ops.kubeactuary.dev", "--all-namespaces"],
        [*prefix, "auth", "can-i", "patch", "operationcapsules/status.ops.kubeactuary.dev", "-n", namespace],
        [*prefix, "top", "pod", "-n", namespace, "-l", CONTROLLER_SELECTOR, "--containers"],
    ]


def print_plan(provider: str, commands: list[list[str]]) -> None:
    print("lightweight-cluster-smoke: plan")
    print(f"provider: {provider}")
    for command in commands:
        print(shlex.join(command))


def write_evidence(
    output: str,
    provider: str,
    namespace: str,
    mode: str,
    commands: list[list[str]],
    records: list[dict[str, object]] | None = None,
) -> None:
    records = records or [{"command": command} for command in commands]
    failed = sum(1 for record in records if record.get("ok") is False)
    report = {
        "schemaVersion": "kube-actuary.lightweight-smoke.v1",
        "provider": provider,
        "namespace": namespace,
        "mode": mode,
        "clusterWrites": "server-side-dry-run-only",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "commands": records,
        "summary": {
            "total": len(records),
            "passed": len(records) - failed,
            "failed": failed,
        },
    }
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True))


def run_commands(commands: list[list[str]], provider: str, namespace: str, output: str | None = None) -> int:
    failed = 0
    records: list[dict[str, object]] = []
    for command in commands:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"{status} {shlex.join(command)}")
        records.append(
            {
                "command": command,
                "exitCode": result.returncode,
                "ok": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if result.returncode != 0:
            failed += 1
            message = (result.stderr or result.stdout).strip()
            if message:
                print(f"  {message.splitlines()[0]}")
    if output:
        write_evidence(output, provider, namespace, "run", commands, records)
    if failed:
        print(f"lightweight-cluster-smoke: failed ({failed}/{len(commands)} failed)")
        return 1
    print("lightweight-cluster-smoke: passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or run lightweight cluster smoke checks.")
    parser.add_argument("--provider", choices=PROVIDERS, required=True)
    parser.add_argument("--namespace", default="kubeactuary-system")
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--run", action="store_true", help="execute checks instead of printing the plan")
    parser.add_argument("--output", help="write structured evidence JSON for the plan or run")
    args = parser.parse_args(argv)

    commands = smoke_commands(args.kubectl, args.namespace)
    if not args.run:
        print_plan(args.provider, commands)
        if args.output:
            write_evidence(args.output, args.provider, args.namespace, "plan", commands)
        return 0
    print(f"lightweight-cluster-smoke: run provider={args.provider}")
    return run_commands(commands, args.provider, args.namespace, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
