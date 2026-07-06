#!/usr/bin/env python3
"""Print or run managed Kubernetes smoke checks for KubeActuary."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRD = "deploy/crds/operationcapsules.ops.kubeactuary.dev.yaml"
PROVIDER_COMMANDS = {
    "eks": "aws --version",
    "gke": "gcloud version",
    "aks": "az version",
}


def split_command(command: str) -> list[str]:
    return shlex.split(command)


def smoke_commands(provider: str, kubectl: str, provider_cli: str | None, namespace: str) -> list[list[str]]:
    provider_prefix = split_command(provider_cli or PROVIDER_COMMANDS[provider])
    kubectl_prefix = split_command(kubectl)
    return [
        provider_prefix,
        [*kubectl_prefix, "version", "--client=true", "-o", "json"],
        [*kubectl_prefix, "version", "-o", "json"],
        [*kubectl_prefix, "apply", "--dry-run=server", "-f", CRD],
        [*kubectl_prefix, "explain", "operationcapsules", "--api-version=ops.kubeactuary.dev/v1alpha1"],
        [*kubectl_prefix, "auth", "can-i", "get", "operationcapsules.ops.kubeactuary.dev", "--all-namespaces"],
        [*kubectl_prefix, "auth", "can-i", "patch", "operationcapsules/status.ops.kubeactuary.dev", "-n", namespace],
    ]


def print_plan(provider: str, commands: list[list[str]]) -> None:
    print("managed-kubernetes-smoke: plan")
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
        "schemaVersion": "kube-actuary.managed-kubernetes-smoke.v1",
        "provider": provider,
        "namespace": namespace,
        "mode": mode,
        "clusterAccess": "current-context",
        "clusterWrites": "server-side-dry-run-only",
        "cloudApi": "version-command-only",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "commands": records,
        "summary": {
            "total": len(records),
            "passed": len(records) - failed,
            "failed": failed,
        },
    }
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True))


def run_commands(
    provider: str,
    namespace: str,
    commands: list[list[str]],
    output: str | None = None,
) -> int:
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
        print(f"managed-kubernetes-smoke: failed ({failed}/{len(commands)} failed)")
        return 1
    print("managed-kubernetes-smoke: passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or run managed Kubernetes smoke checks.")
    parser.add_argument("--provider", choices=tuple(PROVIDER_COMMANDS), required=True)
    parser.add_argument("--namespace", default="kubeactuary-system")
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--provider-cli", help="override provider CLI command")
    parser.add_argument("--run", action="store_true", help="execute checks against the current context")
    parser.add_argument("--output", help="write structured evidence JSON for the plan or run")
    args = parser.parse_args(argv)

    commands = smoke_commands(args.provider, args.kubectl, args.provider_cli, args.namespace)
    if not args.run:
        print_plan(args.provider, commands)
        if args.output:
            write_evidence(args.output, args.provider, args.namespace, "plan", commands)
        return 0
    print(f"managed-kubernetes-smoke: run provider={args.provider}")
    return run_commands(args.provider, args.namespace, commands, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
