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
RUN_REPORT_JSON = ".kubeactuary/next-version-task-run.json"
RUN_REPORT_MD = ".kubeactuary/next-version-task-run.md"
RUNNABLE_CAPTURE_STATUS = "tool-ready"
NON_ERROR_RUN_STATUSES = {"plan", "passed", "blocked-by-environment"}


def load_next_task(evidence_dir: Path) -> dict[str, Any]:
    path = evidence_dir / NEXT_TASK_PATH
    if not path.is_file():
        raise ValueError(
            f"{path}: next-task artifact not found; run "
            f"`python3 -B scripts/prepare_live_evidence_directory.py {evidence_dir}` first"
        )
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


def failure_message(record: dict[str, Any]) -> str | None:
    lines: list[str] = []
    for key in ("stderr", "stdout"):
        value = record.get(key)
        if isinstance(value, str):
            lines.extend(line.strip() for line in value.splitlines() if line.strip())
    for line in lines:
        if line.lower().startswith("error:"):
            return line
    return lines[-1] if lines else None


def failure_summary(records: list[dict[str, Any]], validations: list[dict[str, Any]]) -> dict[str, Any] | None:
    for index, record in enumerate(records, start=1):
        if record.get("ok") is False:
            return {
                "index": index,
                "command": record.get("command"),
                "exitCode": record.get("exitCode"),
                "message": failure_message(record),
            }
    for record in validations:
        if record.get("errors"):
            return {
                "index": record.get("index"),
                "command": record.get("command"),
                "exitCode": None,
                "message": str(record.get("errors", ["validation failed"])[0]),
            }
    return None


def blocked_run_summary(selected: dict[str, Any]) -> dict[str, Any] | None:
    capture_status = selected.get("captureStatus")
    if capture_status == RUNNABLE_CAPTURE_STATUS:
        return None
    if not capture_status:
        capture_status = "not-ready"
    missing_tools = selected.get("missingTools") or []
    next_step = selected.get("nextStep")
    environment_status = selected.get("environmentStatus")
    if missing_tools:
        message = f"missing tools: {', '.join(str(tool) for tool in missing_tools)}"
    elif next_step:
        message = str(next_step)
    elif environment_status:
        message = f"environment status: {environment_status}"
    else:
        message = f"capture status is {capture_status}"
    return {
        "captureStatus": capture_status,
        "environmentStatus": environment_status,
        "missingTools": missing_tools,
        "nextStep": next_step,
        "message": message,
    }


def queue_source(task: dict[str, Any]) -> str:
    return str(task.get("sourceWorklistQueueSource") or task.get("queueSource") or "generated")


def build_result(evidence_dir: Path, run: bool = False) -> dict[str, Any]:
    task = load_next_task(evidence_dir)
    selected = task["selected"]
    source = queue_source(task)
    commands = selected_commands(task)
    validations = validate_commands(commands)
    validation_errors = [error for record in validations for error in record["errors"]]
    records: list[dict[str, Any]] = []
    if run and validation_errors:
        raise ValueError("; ".join(validation_errors))
    blocker = blocked_run_summary(selected) if run else None
    if run and blocker is None:
        for command in commands:
            record = run_command(command)
            records.append(record)
            if record["ok"] is not True:
                break
    status = "failed" if any(record.get("ok") is False for record in records) or validation_errors else "passed"
    if not run:
        status = "plan" if not validation_errors else "failed"
    elif blocker is not None:
        status = str(blocker["captureStatus"])
    failure = failure_summary(records, validations)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "run" if run else "plan",
        "status": status,
        "queueSource": source,
        "clusterWrites": "disabled-or-server-side-dry-run-only",
        "ranAt": datetime.now(timezone.utc).isoformat() if run else None,
        "evidenceDir": str(evidence_dir),
        "nextTask": {
            "schemaVersion": task.get("schemaVersion"),
            "queueSource": source,
            "path": str(evidence_dir / NEXT_TASK_PATH),
            "selected": {
                "id": selected.get("id"),
                "version": selected.get("version"),
                "item": selected.get("item"),
                "kind": selected.get("kind"),
                "captureStatus": selected.get("captureStatus"),
                "environmentStatus": selected.get("environmentStatus"),
                "missingTools": selected.get("missingTools", []),
                "nextStep": selected.get("nextStep"),
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
        "failure": failure,
        "blocker": blocker,
    }


def render_text(result: dict[str, Any]) -> str:
    summary = result["summary"]
    selected = result["nextTask"]["selected"]
    lines = [
        f"next-version-task-run: {result['status']}",
        f"mode: {result['mode']}",
        f"queue-source: {result.get('queueSource', 'generated')}",
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
    failure = result.get("failure")
    if isinstance(failure, dict) and failure.get("message"):
        lines.append(f"failure: {failure.get('message')}")
    blocker = result.get("blocker")
    if isinstance(blocker, dict) and blocker.get("message"):
        lines.append(f"blocker: {blocker.get('message')}")
    return "\n".join(lines) + "\n"


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    selected = result["nextTask"]["selected"]
    lines = [
        "# KubeActuary Next Version Task Run",
        "",
        f"Schema: `{result['schemaVersion']}`",
        f"Mode: `{result['mode']}`",
        f"Status: `{result['status']}`",
        f"Queue source: `{result.get('queueSource', 'generated')}`",
        f"Evidence directory: `{result['evidenceDir']}`",
        f"Cluster writes: `{result['clusterWrites']}`",
        "",
        "## Selected",
        "",
        f"- `{selected.get('id')}` {selected.get('item')} ({selected.get('version')})",
        f"- capture status: `{selected.get('captureStatus')}`",
        f"- kind: `{selected.get('kind')}`",
        "",
        "## Summary",
        "",
        f"- commands: {summary['commands']}",
        f"- valid commands: {summary['validCommands']}",
        f"- ran: {summary['ran']}",
        f"- failed: {summary['failed']}",
        f"- validation errors: {summary['validationErrors']}",
        "",
        "## Commands",
        "",
    ]
    for record in result["validations"]:
        status = "valid" if record["valid"] else "invalid"
        lines.append(f"- `{status}` {record['command']}")
        for error in record["errors"]:
            lines.append(f"  error: {error}")
    if result["records"]:
        lines.extend(["", "## Run Records", ""])
        for record in result["records"]:
            status = "passed" if record.get("ok") else "failed"
            lines.append(f"- `{status}` {record['command']}")
            if record.get("stdoutPath"):
                lines.append(f"  stdout: `{record['stdoutPath']}`")
            if record.get("exitCode") is not None:
                lines.append(f"  exit code: {record['exitCode']}")
    failure = result.get("failure")
    if isinstance(failure, dict) and failure.get("message"):
        lines.extend(["", "## Failure", "", f"- `{failure.get('message')}`"])
    blocker = result.get("blocker")
    if isinstance(blocker, dict) and blocker.get("message"):
        lines.extend(["", "## Blocker", "", f"- `{blocker.get('message')}`"])
    return "\n".join(lines) + "\n"


def record_result(evidence_dir: Path, result: dict[str, Any]) -> dict[str, str]:
    json_path = evidence_dir / RUN_REPORT_JSON
    markdown_path = evidence_dir / RUN_REPORT_MD
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_markdown(result))
    return {"json": str(json_path), "markdown": str(markdown_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or run the selected next version task commands.")
    parser.add_argument("evidence_dir", help="prepared evidence directory with .kubeactuary/next-version-task.json")
    parser.add_argument("--run", action="store_true", help="execute validated selected commands")
    parser.add_argument("--record", action="store_true", help="write run status JSON and Markdown under .kubeactuary")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", "-o", default="-", help="status output path, or '-' for stdout")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    try:
        result = build_result(evidence_dir, run=args.run)
        recorded = record_result(evidence_dir, result) if args.record else None
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
    if recorded:
        print(f"next-version-task-run: recorded {recorded['json']}", file=sys.stderr)
    return 0 if result["status"] in NON_ERROR_RUN_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
