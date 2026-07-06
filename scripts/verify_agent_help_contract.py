#!/usr/bin/env python3
"""Verify machine-readable agent help contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "kube-actuary"
SCHEMA_VERSION = "kube-actuary.help.v1"


def run_help() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(CLI), "help", "agents", "--format", "json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def check_required_fields(payload: dict[str, Any], errors: list[str]) -> None:
    compatibility = payload.get("compatibility")
    if not isinstance(compatibility, dict):
        errors.append("compatibility must be an object")
        return

    if compatibility.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("compatibility schemaVersion mismatch")
    if compatibility.get("introducedIn") != "0.2.3":
        errors.append("introducedIn mismatch")
    if compatibility.get("backwardCompatibleUntil") != "1.0.0":
        errors.append("backwardCompatibleUntil mismatch")

    for field in compatibility.get("requiredTopLevelFields", []):
        if field not in payload:
            errors.append(f"missing top-level field: {field}")

    required_command_fields = compatibility.get("requiredCommandFields", [])
    commands = payload.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("commands must be a non-empty list")
        return
    for command in commands:
        if not isinstance(command, dict):
            errors.append("command entry must be an object")
            continue
        for field in required_command_fields:
            if field not in command:
                errors.append(f"command {command.get('name')} missing field: {field}")


def main() -> int:
    errors: list[str] = []
    result = run_help()
    if result.returncode != 0:
        errors.append(f"help command failed: {result.stderr.strip()}")
        payload: dict[str, Any] = {}
    else:
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"help output is not JSON: {exc}")
            payload = {}

    if payload.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion mismatch")
    check_required_fields(payload, errors)

    if errors:
        print("agent-help-contract: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("agent-help-contract: passed")
    print(f"schemaVersion: {payload['schemaVersion']}")
    print(f"commands: {len(payload['commands'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
