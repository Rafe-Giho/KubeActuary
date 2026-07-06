#!/usr/bin/env python3
"""Advance one selected version task and record before/after iteration history."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.inspect_version_history import inspect_history  # noqa: E402
from scripts.prepare_live_evidence_directory import prepare_directory  # noqa: E402
from scripts.record_version_iteration import record_iteration  # noqa: E402
from scripts.run_next_version_task import build_result as run_next_task  # noqa: E402
from scripts.run_next_version_task import record_result as record_next_task_run  # noqa: E402
from scripts.run_next_version_task import SCHEMA_VERSION as NEXT_TASK_RUN_SCHEMA  # noqa: E402
from scripts.select_next_version_task import build_selection  # noqa: E402


SCHEMA_VERSION = "kube-actuary.version-iteration-advance.v1"
ADVANCE_REPORT_JSON = ".kubeactuary/version-iteration-advance.json"
ADVANCE_REPORT_MD = ".kubeactuary/version-iteration-advance.md"
NEXT_TASK_PATH = ".kubeactuary/next-version-task.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def planned_result(
    evidence_dir: Path,
    history_dir: Path,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
) -> dict[str, Any]:
    selection = build_selection(
        version_filters=[],
        include_complete=False,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
        skip_complete_evidence=True,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
    )
    selected = selection.get("selected") or {}
    queue_source = str(selection.get("sourceWorklistQueueSource") or "generated")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "plan",
        "status": "plan",
        "queueSource": queue_source,
        "clusterWrites": "disabled-or-server-side-dry-run-only",
        "evidenceDir": evidence_dir.as_posix(),
        "historyDir": history_dir.as_posix(),
        "probeEnvironment": probe_environment,
        "kubectl": kubectl,
        "filters": selection.get("filters", {}),
        "environmentProbe": selection.get("environmentProbe"),
        "selected": {
            "id": selected.get("id"),
            "version": selected.get("version"),
            "item": selected.get("item"),
            "kind": selected.get("kind"),
            "captureStatus": selected.get("captureStatus"),
            "environmentStatus": selected.get("environmentStatus"),
            "missingTools": selected.get("missingTools", []),
            "nextStep": selected.get("nextStep"),
            "commands": selected.get("resolvedCommands", selected.get("commands", [])),
        },
        "plannedSteps": [
            "prepare live evidence directory with skip-complete evidence",
            "record before iteration history",
            "run selected next-task evidence commands",
            "refresh next-task artifacts after evidence capture",
            "record after iteration history and diff",
            "inspect version history status",
        ],
    }


def blocked_runner_result(
    evidence_dir: Path,
    next_task: dict[str, Any],
    selected: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    commands = selected.get("resolvedCommands") or selected.get("commands") or []
    queue_source = str(next_task.get("sourceWorklistQueueSource") or "generated")
    return {
        "schemaVersion": NEXT_TASK_RUN_SCHEMA,
        "mode": "run",
        "status": str(selected.get("captureStatus") or "blocked"),
        "queueSource": queue_source,
        "clusterWrites": "disabled-or-server-side-dry-run-only",
        "ranAt": created_at,
        "evidenceDir": str(evidence_dir),
        "nextTask": {
            "schemaVersion": next_task.get("schemaVersion"),
            "queueSource": queue_source,
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
            "validCommands": 0,
            "ran": 0,
            "failed": 0,
            "validationErrors": 0,
        },
        "validations": [],
        "records": [],
        "failure": None,
    }


def run_advance(
    evidence_dir: Path,
    history_dir: Path,
    run_id: str,
    created_at: str,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
) -> dict[str, Any]:
    prepared = prepare_directory(
        evidence_dir,
        skip_complete_evidence=True,
        probe_environment=probe_environment,
        kubectl=kubectl,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
    )
    prepared_next_task = prepared.get("nextTask") or {}
    queue_source = str(prepared_next_task.get("sourceWorklistQueueSource") or "generated")
    before = record_iteration(
        history_dir,
        run_id=f"{run_id}-before",
        created_at=created_at,
        version_filters=[],
        open_only=True,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
        prefer_prepared_queue=True,
    )
    selected = prepared_next_task.get("selected") or {}
    if probe_environment and selected.get("captureStatus") != "tool-ready":
        runner = blocked_runner_result(evidence_dir, prepared_next_task, selected, created_at)
        runner_record = record_next_task_run(evidence_dir, runner)
        blocked = record_iteration(
            history_dir,
            run_id=f"{run_id}-blocked",
            created_at=created_at,
            version_filters=[],
            open_only=True,
            probe_environment=probe_environment,
            kubectl=kubectl,
            evidence_dir=evidence_dir,
            capture_status_filters=capture_status_filters,
            missing_tool_filters=missing_tool_filters,
            environment_status_filters=environment_status_filters,
            prefer_prepared_queue=True,
        )
        history = inspect_history(history_dir)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "run",
            "status": str(selected.get("captureStatus") or "blocked"),
            "queueSource": queue_source,
            "clusterWrites": "disabled-or-server-side-dry-run-only",
            "evidenceDir": evidence_dir.as_posix(),
            "historyDir": history_dir.as_posix(),
            "probeEnvironment": probe_environment,
            "kubectl": kubectl,
            "filters": prepared_next_task.get("filters", {}),
            "environmentProbe": (prepared.get("queue") or {}).get("environmentProbe"),
            "runId": run_id,
            "createdAt": created_at,
            "before": {
                "runId": before.get("runId"),
                "summary": before.get("summary"),
            },
            "runner": runner,
            "runnerRecord": runner_record,
            "after": {
                "runId": blocked.get("runId"),
                "summary": blocked.get("summary"),
                "diffSummary": blocked.get("diffSummary"),
            },
            "nextTask": {
                "schemaVersion": prepared_next_task.get("schemaVersion"),
                "queueSource": queue_source,
                "selected": selected.get("id"),
                "captureStatus": selected.get("captureStatus"),
                "environmentStatus": selected.get("environmentStatus"),
                "missingTools": selected.get("missingTools", []),
                "nextStep": selected.get("nextStep"),
                "skippedCompleteEvidence": prepared_next_task.get("summary", {}).get(
                    "skippedCompleteEvidence",
                    0,
                ),
            },
            "history": history.get("summary", {}),
        }
    runner = run_next_task(evidence_dir, run=True)
    runner_record = record_next_task_run(evidence_dir, runner)
    prepare_directory(
        evidence_dir,
        skip_complete_evidence=True,
        probe_environment=probe_environment,
        kubectl=kubectl,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
    )
    after = record_iteration(
        history_dir,
        run_id=f"{run_id}-after",
        created_at=created_at,
        version_filters=[],
        open_only=True,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
        prefer_prepared_queue=True,
    )
    history = inspect_history(history_dir)
    status = "passed" if runner.get("status") == "passed" and history.get("valid") is True else "failed"
    next_task = json.loads((evidence_dir / ".kubeactuary" / "next-version-task.json").read_text())
    refreshed_selected = next_task.get("selected") or {}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "run",
        "status": status,
        "queueSource": queue_source,
        "clusterWrites": "disabled-or-server-side-dry-run-only",
        "evidenceDir": evidence_dir.as_posix(),
        "historyDir": history_dir.as_posix(),
        "probeEnvironment": probe_environment,
        "kubectl": kubectl,
        "filters": prepared_next_task.get("filters", {}),
        "environmentProbe": (prepared.get("queue") or {}).get("environmentProbe"),
        "runId": run_id,
        "createdAt": created_at,
        "before": {
            "runId": before.get("runId"),
            "summary": before.get("summary"),
        },
        "runner": runner,
        "runnerRecord": runner_record,
        "after": {
            "runId": after.get("runId"),
            "summary": after.get("summary"),
            "diffSummary": after.get("diffSummary"),
        },
        "nextTask": {
            "schemaVersion": next_task.get("schemaVersion"),
            "queueSource": queue_source,
            "selected": refreshed_selected.get("id"),
            "captureStatus": refreshed_selected.get("captureStatus"),
            "environmentStatus": refreshed_selected.get("environmentStatus"),
            "missingTools": refreshed_selected.get("missingTools", []),
            "nextStep": refreshed_selected.get("nextStep"),
            "skippedCompleteEvidence": next_task.get("summary", {}).get("skippedCompleteEvidence", 0),
        },
        "history": history.get("summary", {}),
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [
        f"version-iteration-advance: {result['status']}",
        f"mode: {result['mode']}",
        f"queue-source: {result.get('queueSource', 'generated')}",
        f"evidence-dir: {result['evidenceDir']}",
        f"history-dir: {result['historyDir']}",
        f"cluster-writes: {result['clusterWrites']}",
        f"probe-environment: {str(result.get('probeEnvironment', False)).lower()}",
    ]
    if result["mode"] == "plan":
        selected = result.get("selected", {})
        lines.append(f"selected: {selected.get('id')}")
        if selected.get("captureStatus"):
            lines.append(f"selected-status: {selected.get('captureStatus')}")
        if selected.get("environmentStatus"):
            lines.append(f"selected-environment: {selected.get('environmentStatus')}")
        missing_tools = selected.get("missingTools") or []
        if missing_tools:
            tools = ", ".join(str(tool) for tool in missing_tools)
            lines.append(f"selected-missing-tools: {tools}")
        if selected.get("nextStep"):
            lines.append(f"selected-next-step: {selected.get('nextStep')}")
        for command in selected.get("commands", []):
            lines.append(f"command: {command}")
        for step in result.get("plannedSteps", []):
            lines.append(f"step: {step}")
    else:
        lines.append(f"run-id: {result['runId']}")
        lines.append(f"before-run-id: {result['before']['runId']}")
        if result.get("after"):
            lines.append(f"after-run-id: {result['after']['runId']}")
        lines.append(f"runner-status: {result['runner']['status'] if result.get('runner') else 'not-run'}")
        if result.get("runnerRecord"):
            lines.append(f"runner-record: {result['runnerRecord'].get('json')}")
        lines.append(f"history-runs: {result['history'].get('runs')}")
        lines.append(f"next-task: {result['nextTask'].get('selected')}")
        if result["nextTask"].get("captureStatus"):
            lines.append(f"next-task-status: {result['nextTask'].get('captureStatus')}")
        if result["nextTask"].get("environmentStatus"):
            lines.append(f"next-task-environment: {result['nextTask'].get('environmentStatus')}")
        missing_tools = result["nextTask"].get("missingTools") or []
        if missing_tools:
            tools = ", ".join(str(tool) for tool in missing_tools)
            lines.append(f"next-task-missing-tools: {tools}")
        if result["nextTask"].get("nextStep"):
            lines.append(f"next-task-next-step: {result['nextTask'].get('nextStep')}")
        lines.append(f"skipped-complete-evidence: {result['nextTask'].get('skippedCompleteEvidence')}")
        if result.get("advanceRecord"):
            lines.append(f"advance-record: {result['advanceRecord'].get('json')}")
    return "\n".join(lines) + "\n"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# KubeActuary Version Iteration Advance",
        "",
        f"Schema: `{result['schemaVersion']}`",
        f"Mode: `{result['mode']}`",
        f"Status: `{result['status']}`",
        f"Queue source: `{result.get('queueSource', 'generated')}`",
        f"Evidence directory: `{result['evidenceDir']}`",
        f"History directory: `{result['historyDir']}`",
        f"Cluster writes: `{result['clusterWrites']}`",
        "",
        "## Run",
        "",
    ]
    if result["mode"] == "run":
        lines.append(f"- run id: `{result.get('runId')}`")
        lines.append(f"- before: `{(result.get('before') or {}).get('runId')}`")
        if result.get("after"):
            lines.append(f"- after: `{result['after'].get('runId')}`")
        lines.append(f"- runner: `{(result.get('runner') or {}).get('status', 'not-run')}`")
        if result.get("runnerRecord"):
            lines.append(f"- runner record: `{result['runnerRecord'].get('json')}`")
        next_task = result.get("nextTask") or {}
        lines.append(f"- next task: `{next_task.get('selected')}`")
        if next_task.get("captureStatus"):
            lines.append(f"- next task status: `{next_task.get('captureStatus')}`")
        if next_task.get("environmentStatus"):
            lines.append(f"- next task environment: `{next_task.get('environmentStatus')}`")
        missing_tools = next_task.get("missingTools") or []
        if missing_tools:
            tools = ", ".join(str(tool) for tool in missing_tools)
            lines.append(f"- next task missing tools: `{tools}`")
        if next_task.get("nextStep"):
            lines.append(f"- next task next step: {next_task.get('nextStep')}")
        lines.append(f"- history runs: {result.get('history', {}).get('runs')}")
    else:
        selected = result.get("selected") or {}
        lines.append(f"- selected: `{selected.get('id')}`")
        if selected.get("captureStatus"):
            lines.append(f"- selected status: `{selected.get('captureStatus')}`")
        if selected.get("environmentStatus"):
            lines.append(f"- selected environment: `{selected.get('environmentStatus')}`")
        missing_tools = selected.get("missingTools") or []
        if missing_tools:
            tools = ", ".join(str(tool) for tool in missing_tools)
            lines.append(f"- selected missing tools: `{tools}`")
        if selected.get("nextStep"):
            lines.append(f"- selected next step: {selected.get('nextStep')}")
        for step in result.get("plannedSteps", []):
            lines.append(f"- planned step: {step}")
    return "\n".join(lines) + "\n"


def record_advance_result(evidence_dir: Path, result: dict[str, Any]) -> dict[str, str]:
    json_path = evidence_dir / ADVANCE_REPORT_JSON
    markdown_path = evidence_dir / ADVANCE_REPORT_MD
    json_path.parent.mkdir(parents=True, exist_ok=True)
    record = {"json": str(json_path), "markdown": str(markdown_path)}
    result["advanceRecord"] = record
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_markdown(result))
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Advance one selected KubeActuary version task.")
    parser.add_argument("evidence_dir")
    parser.add_argument("history_dir")
    parser.add_argument("--run", action="store_true", help="execute the selected safe evidence commands")
    parser.add_argument("--run-id", help="stable run id prefix; defaults to UTC timestamp")
    parser.add_argument("--created-at", help="stable timestamp for tests")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    parser.add_argument("--capture-status", action="append", default=[], help="filter next-task selection by capture status; repeatable")
    parser.add_argument("--missing-tool", action="append", default=[], help="filter next-task selection by missing tool; repeatable")
    parser.add_argument("--environment-status", action="append", default=[], help="filter next-task selection by environment status; repeatable")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--output", "-o", default="-", help="status output path, or '-' for stdout")
    args = parser.parse_args(argv)

    created_at = args.created_at or utc_now()
    run_id = args.run_id or created_at.replace(":", "").replace("+", "z")
    evidence_dir = Path(args.evidence_dir)
    history_dir = Path(args.history_dir)
    try:
        if args.run:
            result = run_advance(
                evidence_dir,
                history_dir,
                run_id=run_id,
                created_at=created_at,
                probe_environment=args.probe_environment,
                kubectl=args.kubectl,
                capture_status_filters=args.capture_status,
                missing_tool_filters=args.missing_tool,
                environment_status_filters=args.environment_status,
            )
            record_advance_result(evidence_dir, result)
        else:
            result = planned_result(
                evidence_dir,
                history_dir,
                probe_environment=args.probe_environment,
                kubectl=args.kubectl,
                capture_status_filters=args.capture_status,
                missing_tool_filters=args.missing_tool,
                environment_status_filters=args.environment_status,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("version-iteration-advance: failed")
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
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        print(f"version-iteration-advance: wrote {args.output}")
    return 0 if result["status"] in {"plan", "passed", "blocked-by-environment"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
