#!/usr/bin/env python3
"""Plan or run the selected next unblock action verifier commands."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "kube-actuary.next-unblock-action-run.v1"
NEXT_ACTION_SCHEMA = "kube-actuary.next-unblock-action.v1"
NEXT_ACTION_PATH = ".kubeactuary/next-unblock-action.json"
RUN_REPORT_JSON = ".kubeactuary/next-unblock-action-run.json"
RUN_REPORT_MD = ".kubeactuary/next-unblock-action-run.md"
NON_ERROR_STATUSES = {"plan", "passed", "clear"}
ALLOWED_VERIFY_COMMANDS = {
    ("az", "version"),
    ("gcloud", "version"),
    ("helm", "version"),
    ("k3s", "--version"),
    ("kind", "version"),
    ("kubectl", "version", "--client=true"),
    ("kubectl", "krew", "version"),
    ("kubectl", "cluster-info", "--request-timeout=5s"),
    ("microk8s", "version"),
    ("minikube", "version"),
}


def load_next_action(evidence_dir: Path) -> dict[str, Any]:
    path = evidence_dir / NEXT_ACTION_PATH
    if not path.is_file():
        raise ValueError(
            f"{path}: next-unblock artifact not found; run "
            f"`python3 -B scripts/prepare_live_evidence_directory.py {evidence_dir}` first"
        )
    payload = json.loads(path.read_text())
    if payload.get("schemaVersion") != NEXT_ACTION_SCHEMA:
        raise ValueError(f"{path}: unsupported next-unblock schemaVersion: {payload.get('schemaVersion')!r}")
    selected = payload.get("selected")
    if selected is not None and not isinstance(selected, dict):
        raise ValueError(f"{path}: selected next unblock action must be an object or null")
    return payload


def command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"invalid command quoting: {command}: {exc}") from exc


def normalized_tokens(tokens: list[str]) -> tuple[str, ...]:
    if not tokens:
        return ()
    return tuple([Path(tokens[0]).name, *tokens[1:]])


def selected_verify_commands(action: dict[str, Any]) -> list[str]:
    selected = action.get("selected")
    if not isinstance(selected, dict):
        return []
    commands = (selected.get("commands") or {}).get("verify") or []
    if not all(isinstance(command, str) for command in commands):
        raise ValueError("selected next unblock verify commands must be strings")
    return list(commands)


def validate_commands(commands: list[str]) -> list[dict[str, Any]]:
    validations: list[dict[str, Any]] = []
    for index, command in enumerate(commands, start=1):
        errors: list[str] = []
        try:
            tokens = command_tokens(command)
        except ValueError as exc:
            tokens = []
            errors.append(str(exc))
        if any(token in {">", ">>", "|", "&&", "||", ";"} for token in tokens):
            errors.append("verify command must not contain shell control operators")
        normalized = normalized_tokens(tokens)
        if normalized not in ALLOWED_VERIFY_COMMANDS:
            errors.append("verify command is not in the next-unblock allowlist")
        validations.append(
            {
                "index": index,
                "command": command,
                "normalized": list(normalized),
                "valid": not errors,
                "errors": errors,
            }
        )
    return validations


def run_command(command: str) -> dict[str, Any]:
    tokens = command_tokens(command)
    record: dict[str, Any] = {"command": command}
    try:
        result = subprocess.run(
            tokens,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        record["stdout"] = result.stdout
        record["stderr"] = result.stderr
        record["exitCode"] = result.returncode
    except FileNotFoundError as exc:
        record["stdout"] = ""
        record["stderr"] = str(exc)
        record["exitCode"] = 127
    record["ok"] = record["exitCode"] == 0
    return record


def failure_message(record: dict[str, Any]) -> str | None:
    lines: list[str] = []
    for key in ("stderr", "stdout"):
        value = record.get(key)
        if isinstance(value, str):
            lines.extend(line.strip() for line in value.splitlines() if line.strip())
    return lines[-1] if lines else None


def failure_summary(records: list[dict[str, Any]], validations: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in records:
        if record.get("ok") is False:
            return {
                "command": record.get("command"),
                "exitCode": record.get("exitCode"),
                "message": failure_message(record),
            }
    for record in validations:
        if record.get("errors"):
            return {
                "command": record.get("command"),
                "exitCode": None,
                "message": str(record.get("errors", ["validation failed"])[0]),
            }
    return None


def selected_summary(action: dict[str, Any]) -> dict[str, Any]:
    selected = action.get("selected") if isinstance(action.get("selected"), dict) else {}
    return {
        "id": selected.get("id"),
        "kind": selected.get("kind"),
        "target": selected.get("tool") or selected.get("environmentStatus"),
        "tool": selected.get("tool"),
        "environmentStatus": selected.get("environmentStatus"),
        "environmentReason": selected.get("environmentReason"),
        "items": selected.get("items", 0),
        "affectedVersions": selected.get("affectedVersions", []),
        "nextStep": selected.get("nextStep"),
    }


def build_result(evidence_dir: Path, run: bool = False) -> dict[str, Any]:
    action = load_next_action(evidence_dir)
    commands = selected_verify_commands(action)
    validations = validate_commands(commands)
    validation_errors = [error for record in validations for error in record["errors"]]
    records: list[dict[str, Any]] = []
    if run and validation_errors:
        status = "failed"
    elif run and not action.get("selected"):
        status = "clear"
    elif run:
        for command in commands:
            record = run_command(command)
            records.append(record)
            if record["ok"] is not True:
                break
        status = "passed" if records and all(record.get("ok") is True for record in records) else "blocked"
    else:
        status = "plan" if not validation_errors else "failed"
    failure = failure_summary(records, validations)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "run" if run else "plan",
        "status": status,
        "clusterWrites": "disabled",
        "ranAt": datetime.now(timezone.utc).isoformat() if run else None,
        "evidenceDir": evidence_dir.as_posix(),
        "nextUnblockAction": {
            "schemaVersion": action.get("schemaVersion"),
            "queueSource": action.get("sourceWorklistQueueSource") or "generated",
            "path": (evidence_dir / NEXT_ACTION_PATH).as_posix(),
            "selected": selected_summary(action),
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
    }


def render_text(result: dict[str, Any]) -> str:
    summary = result["summary"]
    selected = result["nextUnblockAction"]["selected"]
    lines = [
        f"next-unblock-action-run: {result['status']}",
        f"mode: {result['mode']}",
        f"queue-source: {result['nextUnblockAction'].get('queueSource', 'generated')}",
        f"action: {selected.get('id')}",
        f"target: {selected.get('target')}",
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
        if record.get("exitCode") is not None:
            lines.append(f"exit-code: {record.get('exitCode')}")
    failure = result.get("failure")
    if isinstance(failure, dict) and failure.get("message"):
        lines.append(f"blocker: {failure.get('message')}")
    return "\n".join(lines) + "\n"


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    selected = result["nextUnblockAction"]["selected"]
    lines = [
        "# KubeActuary Next Unblock Action Run",
        "",
        f"Schema: `{result['schemaVersion']}`",
        f"Mode: `{result['mode']}`",
        f"Status: `{result['status']}`",
        f"Queue source: `{result['nextUnblockAction'].get('queueSource', 'generated')}`",
        f"Evidence directory: `{result['evidenceDir']}`",
        f"Cluster writes: `{result['clusterWrites']}`",
        "",
        "## Selected",
        "",
        f"- `{selected.get('id')}` target=`{selected.get('target')}` items={selected.get('items', 0)}",
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
            if record.get("exitCode") is not None:
                lines.append(f"  exit code: {record.get('exitCode')}")
    failure = result.get("failure")
    if isinstance(failure, dict) and failure.get("message"):
        lines.extend(["", "## Blocker", "", f"- `{failure.get('message')}`"])
    return "\n".join(lines) + "\n"


def render_payload(result: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(result, indent=2, sort_keys=True) + "\n"
    if fmt == "markdown":
        return render_markdown(result)
    return render_text(result)


def record_result(evidence_dir: Path, result: dict[str, Any]) -> dict[str, str]:
    json_path = evidence_dir / RUN_REPORT_JSON
    md_path = evidence_dir / RUN_REPORT_MD
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_markdown(result))
    return {"json": json_path.as_posix(), "markdown": md_path.as_posix()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or run the selected next unblock action verifier.")
    parser.add_argument("evidence_dir", help="prepared evidence directory with .kubeactuary/next-unblock-action.json")
    parser.add_argument("--run", action="store_true", help="execute selected verify commands only")
    parser.add_argument("--record", action="store_true", help="write run status JSON and Markdown under .kubeactuary")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--output", "-o", default="-", help="status output path, or '-' for stdout")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir)
    try:
        result = build_result(evidence_dir, run=args.run)
        recorded = record_result(evidence_dir, result) if args.record else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("next-unblock-action-run: failed")
        print(f"error: {exc}")
        return 1

    rendered = render_payload(result, args.format)
    if args.output == "-":
        print(rendered, end="")
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        print(f"next-unblock-action-run: wrote {args.output}")
    if recorded:
        print(f"next-unblock-action-run: recorded {recorded['json']}", file=sys.stderr)
    return 0 if result["status"] in NON_ERROR_STATUSES else 1


if __name__ == "__main__":
    raise SystemExit(main())
