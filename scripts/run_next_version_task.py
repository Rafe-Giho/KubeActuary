#!/usr/bin/env python3
"""Plan or run the selected next version task evidence commands."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_external_gate_command_safety import validate_command  # noqa: E402


SCHEMA_VERSION = "kube-actuary.next-version-task-run.v1"
NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"
NEXT_TASK_PATH = ".kubeactuary/next-version-task.json"


def load_next_task(evidence_dir: Path) -> dict[str, Any]:
    path = evidence_dir / NEXT_TASK_PATH
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_TASK_SCHEMA:
        raise ValueError(f"{path}: unsupported next-task schemaVersion: {payload.get('schemaVersion')!r}")
    selected = payload.get("selected")
    if not isinstance(selected, dict):
        raise ValueError(f"{path}: selected next task must be an object")
    return payload


def selected_commands(task: dict[str, Any]) -> list[str]:
    selected = task["selected"]
    commands = selected.get("resolvedCommands") or selected.get("commands") or []
    if not all(isinstance(command, str) for command in commands):
        raise ValueError("selected next task commands must be strings")
    unresolved = [command for command in commands if "<" in command or ">" in command and " > " not in command]
    if unresolved:
        raise ValueError(f"selected next task contains unresolved placeholders: {unresolved[0]}")
    return list(commands)


def validate_commands(commands: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, command in enumerate(commands, start=1):
        errors, prefix = validate_command(f"next-task:{index}", command)
        records.append(
            {
                "index": index,
                "command": command,
                "prefix": prefix,
                "valid": not errors,
                "errors": errors,
            }
        )
    return records


def command_tokens(command: str) -> tuple[list[str], str | None]:
    tokens = shlex.split(command)
    if ">" not in tokens:
        return tokens, None
    redirect_index = tokens.index(">")
    return tokens[:redirect_index], tokens[redirect_index + 1]


def run_command(command: str) -> dict[str, Any]:
    tokens, stdout_path = command_tokens(command)
    record: dict[str, Any] = {
        "command": command,
        "stdoutPath": stdout_path,
    }
    if stdout_path is None:
        result = subprocess.run(
            tokens,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        record["stdout"] = result.stdout
    else:
        output = Path(stdout_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w") as stdout:
            result = subprocess.run(
                tokens,
                cwd=ROOT,
                text=True,
                stdout=stdout,
                stderr=subprocess.PIPE,
                check=False,
            )
        record["stdout"] = ""
    record["stderr"] = result.stderr
    record["exitCode"] = result.returncode
    record["ok"] = result.returncode == 0
    return record


def build_result(evidence_dir: Path, run: bool = False) -> dict[str, Any]:
    task = load_next_task(evidence_dir)
    selected = task["selected"]
    commands = selected_commands(task)
    validations = validate_commands(commands)
    validation_errors = [error for record in validations for error in record["errors"]]
    records: list[dict[str, Any]] = []
    if run and validation_errors:
        raise ValueError("; ".join(validation_errors))
    if run:
        for command in commands:
            record = run_command(command)
            records.append(record)
            if record["ok"] is not True:
                break
    status = "failed" if any(record.get("ok") is False for record in records) or validation_errors else "passed"
    if not run:
        status = "plan" if not validation_errors else "failed"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "run" if run else "plan",
        "status": status,
        "clusterWrites": "disabled-or-server-side-dry-run-only",
        "ranAt": datetime.now(timezone.utc).isoformat() if run else None,
        "evidenceDir": str(evidence_dir),
        "nextTask": {
            "schemaVersion": task.get("schemaVersion"),
            "path": str(evidence_dir / NEXT_TASK_PATH),
            "selected": {
                "id": selected.get("id"),
                "version": selected.get("version"),
                "item": selected.get("item"),
                "kind": selected.get("kind"),
                "captureStatus": selected.get("captureStatus"),
            },
        },
        "summary": {
            "commands": len(commands),
            "validCommands": sum(1 for record in validations if record["valid"]),
            "ran": len(records),
            "failed": sum(1 for record in records if record.get("ok") is False),
            "validationErrors": len(validation_errors),
        },
        "validations": validations,
        "records": records,
    }


def render_text(result: dict[str, Any]) -> str:
    summary = result["summary"]
    selected = result["nextTask"]["selected"]
    lines = [
        f"next-version-task-run: {result['status']}",
        f"mode: {result['mode']}",
        f"task: {selected.get('id')}",
        f"commands: {summary['commands']}",
        f"valid-commands: {summary['validCommands']}",
        f"ran: {summary['ran']}",
        f"failed: {summary['failed']}",
        f"cluster-writes: {result['clusterWrites']}",
    ]
    for record in result["validations"]:
        lines.append(f"command: {record['command']}")
        for error in record["errors"]:
            lines.append(f"error: {error}")
    for record in result["records"]:
        status = "PASS" if record.get("ok") else "FAIL"
        lines.append(f"{status} {record['command']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or run the selected next version task commands.")
    parser.add_argument("evidence_dir", help="prepared evidence directory with .kubeactuary/next-version-task.json")
    parser.add_argument("--run", action="store_true", help="execute validated selected commands")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", "-o", default="-", help="status output path, or '-' for stdout")
    args = parser.parse_args(argv)

    try:
        result = build_result(Path(args.evidence_dir), run=args.run)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("next-version-task-run: failed")
        print(f"error: {exc}")
        return 1

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_text(result)
    if args.output == "-":
        print(rendered, end="")
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        print(f"next-version-task-run: wrote {args.output}")
    return 0 if result["status"] in {"plan", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
