#!/usr/bin/env python3
"""Print or run Helm chart smoke checks for KubeActuary."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHART = "charts/kubeactuary"
CHART_CRD = "charts/kubeactuary/crds/operationcapsules.ops.kubeactuary.dev.yaml"


def split_command(command: str) -> list[str]:
    return shlex.split(command)


def smoke_commands(helm: str, kubectl: str, release: str, namespace: str) -> list[list[str]]:
    helm_prefix = split_command(helm)
    kubectl_prefix = split_command(kubectl)
    return [
        [*helm_prefix, "template", release, CHART, "--set", "controller.enabled=false"],
        [*helm_prefix, "template", release, CHART, "--set", "controller.enabled=true"],
        [*kubectl_prefix, "apply", "--dry-run=server", "-f", CHART_CRD],
        [
            *helm_prefix,
            "install",
            release,
            CHART,
            "--namespace",
            namespace,
            "--create-namespace",
            "--set",
            "controller.enabled=true",
            "--dry-run",
            "--debug",
        ],
    ]


def print_plan(commands: list[list[str]]) -> None:
    print("helm-smoke: plan")
    for command in commands:
        print(shlex.join(command))


def write_evidence(
    output: str,
    release: str,
    namespace: str,
    mode: str,
    commands: list[list[str]],
    records: list[dict[str, object]] | None = None,
) -> None:
    records = records or [{"command": command} for command in commands]
    failed = sum(1 for record in records if record.get("ok") is False)
    report = {
        "schemaVersion": "kube-actuary.helm-smoke.v1",
        "release": release,
        "namespace": namespace,
        "chart": CHART,
        "mode": mode,
        "clusterWrites": "dry-run-only",
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
    commands: list[list[str]],
    release: str,
    namespace: str,
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
        write_evidence(output, release, namespace, "run", commands, records)
    if failed:
        print(f"helm-smoke: failed ({failed}/{len(commands)} failed)")
        return 1
    print("helm-smoke: passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or run Helm chart smoke checks.")
    parser.add_argument("--release", default="kubeactuary")
    parser.add_argument("--namespace", default="kubeactuary-system")
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--run", action="store_true", help="execute dry-run checks instead of printing the plan")
    parser.add_argument("--output", help="write structured evidence JSON for the plan or run")
    args = parser.parse_args(argv)

    commands = smoke_commands(args.helm, args.kubectl, args.release, args.namespace)
    if not args.run:
        print_plan(commands)
        if args.output:
            write_evidence(args.output, args.release, args.namespace, "plan", commands)
        return 0
    print(f"helm-smoke: run release={args.release} namespace={args.namespace}")
    return run_commands(commands, args.release, args.namespace, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
