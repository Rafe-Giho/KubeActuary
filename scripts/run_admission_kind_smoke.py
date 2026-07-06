#!/usr/bin/env python3
"""Print or run optional admission kind smoke checks for KubeActuary."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBHOOK = "deploy/admission/validatingwebhookconfiguration.yaml"


def split_command(command: str) -> list[str]:
    return shlex.split(command)


def smoke_commands(kubectl: str, python: str) -> list[list[str]]:
    kubectl_prefix = split_command(kubectl)
    python_prefix = split_command(python)
    return [
        [*kubectl_prefix, "version", "--client=true", "-o", "json"],
        [*kubectl_prefix, "apply", "--dry-run=server", "-f", WEBHOOK],
        [*python_prefix, "-B", "scripts/verify_admission_policy.py"],
        [*python_prefix, "-B", "scripts/verify_admission_response.py"],
        [*python_prefix, "-B", "scripts/verify_admission_server.py"],
    ]


def print_plan(commands: list[list[str]]) -> None:
    print("admission-kind-smoke: plan")
    for command in commands:
        print(shlex.join(command))


def write_evidence(
    output: str,
    mode: str,
    commands: list[list[str]],
    records: list[dict[str, object]] | None = None,
) -> None:
    records = records or [{"command": command} for command in commands]
    failed = sum(1 for record in records if record.get("ok") is False)
    report = {
        "schemaVersion": "kube-actuary.admission-kind-smoke.v1",
        "mode": mode,
        "clusterWrites": "server-side-dry-run-only",
        "localServer": "loopback-only",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "commands": records,
        "summary": {
            "total": len(records),
            "passed": len(records) - failed,
            "failed": failed,
        },
    }
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True))


def run_commands(commands: list[list[str]], output: str | None = None) -> int:
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
        write_evidence(output, "run", commands, records)
    if failed:
        print(f"admission-kind-smoke: failed ({failed}/{len(commands)} failed)")
        return 1
    print("admission-kind-smoke: passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or run optional admission kind smoke checks.")
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--run", action="store_true", help="execute smoke checks instead of printing the plan")
    parser.add_argument("--output", help="write structured evidence JSON for the plan or run")
    args = parser.parse_args(argv)

    commands = smoke_commands(args.kubectl, args.python)
    if not args.run:
        print_plan(commands)
        if args.output:
            write_evidence(args.output, "plan", commands)
        return 0
    print("admission-kind-smoke: run")
    return run_commands(commands, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
