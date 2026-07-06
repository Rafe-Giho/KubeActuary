#!/usr/bin/env python3
"""Print or run Krew manifest install smoke checks for KubeActuary."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def split_command(command: str) -> list[str]:
    return shlex.split(command)


def smoke_command(kubectl: str, manifest: str) -> list[str]:
    return [*split_command(kubectl), "krew", "install", "--manifest", manifest]


def print_plan(command: list[str], krew_root: str) -> None:
    print("krew-smoke: plan")
    print(f"KREW_ROOT={shlex.quote(krew_root)} {shlex.join(command)}")


def write_evidence(
    output: str,
    manifest: str,
    krew_root: str,
    mode: str,
    command: list[str],
    record: dict[str, object] | None = None,
) -> None:
    record = record or {"command": command, "env": {"KREW_ROOT": krew_root}}
    failed = 1 if record.get("ok") is False else 0
    report = {
        "schemaVersion": "kube-actuary.krew-smoke.v1",
        "manifest": manifest,
        "mode": mode,
        "clusterAccess": "none",
        "filesystemWrites": "isolated-krew-root",
        "network": "depends-on-manifest-uri",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "commands": [record],
        "summary": {
            "total": 1,
            "passed": 1 - failed,
            "failed": failed,
        },
    }
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True))


def run_command(command: list[str], manifest: str, krew_root: str, output: str | None = None) -> int:
    env = dict(os.environ)
    env["KREW_ROOT"] = krew_root
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"{status} KREW_ROOT={shlex.quote(krew_root)} {shlex.join(command)}")
    record = {
        "command": command,
        "env": {"KREW_ROOT": krew_root},
        "exitCode": result.returncode,
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    if output:
        write_evidence(output, manifest, krew_root, "run", command, record)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        if message:
            print(f"  {message.splitlines()[0]}")
        print("krew-smoke: failed")
        return result.returncode
    print("krew-smoke: passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or run Krew manifest install smoke checks.")
    parser.add_argument("--manifest", default="dist/actuary.yaml")
    parser.add_argument("--kubectl", default="kubectl")
    parser.add_argument("--krew-root", help="isolated KREW_ROOT for run mode")
    parser.add_argument("--run", action="store_true", help="execute the install smoke instead of printing the plan")
    parser.add_argument("--output", help="write structured evidence JSON for the plan or run")
    args = parser.parse_args(argv)

    command = smoke_command(args.kubectl, args.manifest)
    if not args.run:
        krew_root = args.krew_root or "<isolated-krew-root>"
        print_plan(command, krew_root)
        if args.output:
            write_evidence(args.output, args.manifest, krew_root, "plan", command)
        return 0

    if args.krew_root:
        Path(args.krew_root).mkdir(parents=True, exist_ok=True)
        return run_command(command, args.manifest, args.krew_root, output=args.output)

    with tempfile.TemporaryDirectory(prefix="kubeactuary-krew-") as krew_root:
        return run_command(command, args.manifest, krew_root, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
