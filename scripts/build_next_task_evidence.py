#!/usr/bin/env python3
"""Build local supplemental evidence for the selected next task."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_external_evidence import KINDS, build_record  # noqa: E402


SCHEMA_VERSION = "kube-actuary.next-task-evidence-build.v1"
NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"
BUILDER_SCRIPT = "scripts/build_external_evidence.py"
BUILD_REPORT_JSON = ".kubeactuary/next-task-evidence-build.json"
BUILD_REPORT_MD = ".kubeactuary/next-task-evidence-build.md"


def rooted(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def option(tokens: list[str], name: str) -> str | None:
    if name not in tokens:
        return None
    index = tokens.index(name)
    if index + 1 >= len(tokens):
        return None
    return tokens[index + 1]


def load_next_task(evidence_dir: Path) -> dict[str, Any]:
    path = evidence_dir / ".kubeactuary" / "next-version-task.json"
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


def build_specs(selected: dict[str, Any]) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for command in selected.get("resolvedCommands", []):
        try:
            tokens = shlex.split(command)
        except ValueError:
            continue
        if not any(token.endswith(BUILDER_SCRIPT) for token in tokens):
            continue
        kind = option(tokens, "--kind")
        source = option(tokens, "--source")
        output = option(tokens, "--output")
        if kind not in KINDS or source is None or output is None:
            continue
        specs.append({"command": command, "kind": kind, "source": source, "output": output})
    return specs


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def build_next_task_evidence(evidence_dir: Path, force: bool = False) -> dict[str, Any]:
    task = load_next_task(evidence_dir)
    selected = task["selected"]
    specs = build_specs(selected)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for spec in specs:
        source = rooted(spec["source"])
        output = rooted(spec["output"])
        item = {
            "kind": spec["kind"],
            "source": str(source),
            "output": str(output),
            "command": spec["command"],
            "status": "pending",
        }
        if not source.is_file():
            item["status"] = "missing-source"
            errors.append(f"missing source: {source}")
        elif output.exists() and not force:
            item["status"] = "output-exists"
        else:
            record = build_record(spec["kind"], source)
            write_json(output, record)
            item["status"] = "built" if record.get("ok") is True else "failed"
            item["ok"] = record.get("ok")
            if record.get("ok") is not True:
                errors.append(f"evidence check failed: {output}")
        records.append(item)
    if not specs:
        errors.append("selected next task has no local supplemental evidence build command")
    built = sum(1 for item in records if item["status"] == "built")
    skipped = sum(1 for item in records if item["status"] == "output-exists")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "evidenceDir": str(evidence_dir),
        "nextTask": {
            "schemaVersion": task.get("schemaVersion"),
            "path": str(evidence_dir / ".kubeactuary" / "next-version-task.json"),
            "selected": {
                "id": selected.get("id"),
                "version": selected.get("version"),
                "item": selected.get("item"),
                "kind": selected.get("kind"),
                "captureStatus": selected.get("captureStatus"),
            },
        },
        "summary": {
            "status": "failed" if errors else "passed",
            "buildableCommands": len(specs),
            "built": built,
            "skipped": skipped,
            "errors": len(errors),
        },
        "records": records,
        "errors": errors,
    }


def render_text(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"next-task-evidence: {summary['status']}",
        f"buildable: {summary['buildableCommands']}",
        f"built: {summary['built']}",
        f"skipped: {summary['skipped']}",
        f"errors: {summary['errors']}",
    ]
    for item in result["records"]:
        lines.append(f"{item['status']}: {item['kind']} -> {item['output']}")
    for error in result["errors"]:
        lines.append(f"error: {error}")
    return "\n".join(lines) + "\n"


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    selected = result["nextTask"]["selected"]
    lines = [
        "# KubeActuary Next Task Evidence Build",
        "",
        f"Schema: `{result['schemaVersion']}`",
        f"Status: `{summary['status']}`",
        f"Evidence directory: `{result['evidenceDir']}`",
        "",
        "## Selected",
        "",
        f"- `{selected.get('id')}` {selected.get('item')} ({selected.get('version')})",
        f"- capture status: `{selected.get('captureStatus')}`",
        f"- kind: `{selected.get('kind')}`",
        "",
        "## Summary",
        "",
        f"- buildable commands: {summary['buildableCommands']}",
        f"- built: {summary['built']}",
        f"- skipped: {summary['skipped']}",
        f"- errors: {summary['errors']}",
        "",
        "## Records",
        "",
    ]
    if result["records"]:
        for item in result["records"]:
            lines.append(f"- `{item['status']}` `{item['kind']}`")
            lines.append(f"  - source: `{item['source']}`")
            lines.append(f"  - output: `{item['output']}`")
            lines.append(f"  - command: `{item['command']}`")
    else:
        lines.append("- none")
    if result["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in result["errors"]:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def record_result(evidence_dir: Path, result: dict[str, Any]) -> dict[str, str]:
    json_path = evidence_dir / BUILD_REPORT_JSON
    markdown_path = evidence_dir / BUILD_REPORT_MD
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_markdown(result))
    return {"json": str(json_path), "markdown": str(markdown_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build supplemental evidence for the selected next task.")
    parser.add_argument("evidence_dir", help="prepared evidence directory with .kubeactuary/next-version-task.json")
    parser.add_argument("--force", action="store_true", help="overwrite an existing supplemental evidence output")
    parser.add_argument("--record", action="store_true", help="write build status JSON and Markdown under .kubeactuary")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", "-o", default="-", help="status output path, or '-' for stdout")
    args = parser.parse_args(argv)

    try:
        evidence_dir = Path(args.evidence_dir)
        result = build_next_task_evidence(evidence_dir, force=args.force)
        recorded = record_result(evidence_dir, result) if args.record else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("next-task-evidence: failed")
        print(f"error: {exc}")
        return 1

    if args.format == "json":
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    elif args.format == "markdown":
        rendered = render_markdown(result)
    else:
        rendered = render_text(result)
    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"next-task-evidence: wrote {args.output}")
    if recorded:
        print(f"next-task-evidence: recorded {recorded['json']}", file=sys.stderr)
    return 0 if result["summary"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
