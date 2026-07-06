#!/usr/bin/env python3
"""Run or print lightweight cluster smoke checks for KubeActuary."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
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


def run_commands(commands: list[list[str]]) -> int:
    failed = 0
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
        if result.returncode != 0:
            failed += 1
            message = (result.stderr or result.stdout).strip()
            if message:
                print(f"  {message.splitlines()[0]}")
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
    args = parser.parse_args(argv)

    commands = smoke_commands(args.kubectl, args.namespace)
    if not args.run:
        print_plan(args.provider, commands)
        return 0
    print(f"lightweight-cluster-smoke: run provider={args.provider}")
    return run_commands(commands)


if __name__ == "__main__":
    raise SystemExit(main())
