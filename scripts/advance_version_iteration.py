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
) -> dict[str, Any]:
    selection = build_selection(
        version_filters=[],
        include_complete=False,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
        skip_complete_evidence=True,
    )
    selected = selection.get("selected") or {}
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "plan",
        "status": "plan",
        "clusterWrites": "disabled-or-server-side-dry-run-only",
        "evidenceDir": evidence_dir.as_posix(),
        "historyDir": history_dir.as_posix(),
        "probeEnvironment": probe_environment,
        "kubectl": kubectl,
        "environmentProbe": selection.get("environmentProbe"),
        "selected": {
            "id": selected.get("id"),
            "version": selected.get("version"),
            "item": selected.get("item"),
            "kind": selected.get("kind"),
            "captureStatus": selected.get("captureStatus"),
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
    return {
        "schemaVersion": NEXT_TASK_RUN_SCHEMA,
        "mode": "run",
        "status": str(selected.get("captureStatus") or "blocked"),
        "clusterWrites": "disabled-or-server-side-dry-run-only",
        "ranAt": created_at,
        "evidenceDir": str(evidence_dir),
        "nextTask": {
            "schemaVersion": next_task.get("schemaVersion"),
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
) -> dict[str, Any]:
    prepared = prepare_directory(
        evidence_dir,
        skip_complete_evidence=True,
        probe_environment=probe_environment,
        kubectl=kubectl,
    )
    before = record_iteration(
        history_dir,
        run_id=f"{run_id}-before",
        created_at=created_at,
        version_filters=[],
        open_only=True,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
    )
    selected = (prepared.get("nextTask") or {}).get("selected") or {}
    if probe_environment and selected.get("captureStatus") != "tool-ready":
        runner = blocked_runner_result(evidence_dir, prepared.get("nextTask") or {}, selected, created_at)
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
        )
        history = inspect_history(history_dir)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "mode": "run",
            "status": str(selected.get("captureStatus") or "blocked"),
            "clusterWrites": "disabled-or-server-side-dry-run-only",
            "evidenceDir": evidence_dir.as_posix(),
            "historyDir": history_dir.as_posix(),
            "probeEnvironment": probe_environment,
            "kubectl": kubectl,
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
                "schemaVersion": (prepared.get("nextTask") or {}).get("schemaVersion"),
                "selected": selected.get("id"),
                "captureStatus": selected.get("captureStatus"),
                "environmentStatus": selected.get("environmentStatus"),
                "skippedCompleteEvidence": (prepared.get("nextTask") or {}).get("summary", {}).get(
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
    )
    history = inspect_history(history_dir)
    status = "passed" if runner.get("status") == "passed" and history.get("valid") is True else "failed"
    next_task = json.loads((evidence_dir / ".kubeactuary" / "next-version-task.json").read_text())
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "run",
        "status": status,
        "clusterWrites": "disabled-or-server-side-dry-run-only",
        "evidenceDir": evidence_dir.as_posix(),
        "historyDir": history_dir.as_posix(),
        "probeEnvironment": probe_environment,
        "kubectl": kubectl,
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
            "selected": (next_task.get("selected") or {}).get("id"),
            "skippedCompleteEvidence": next_task.get("summary", {}).get("skippedCompleteEvidence", 0),
        },
        "history": history.get("summary", {}),
    }


def render_text(result: dict[str, Any]) -> str:
    lines = [
        f"version-iteration-advance: {result['status']}",
        f"mode: {result['mode']}",
        f"evidence-dir: {result['evidenceDir']}",
        f"history-dir: {result['historyDir']}",
        f"cluster-writes: {result['clusterWrites']}",
        f"probe-environment: {str(result.get('probeEnvironment', False)).lower()}",
    ]
    if result["mode"] == "plan":
        selected = result.get("selected", {})
        lines.append(f"selected: {selected.get('id')}")
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
        lines.append(f"- history runs: {result.get('history', {}).get('runs')}")
    else:
        selected = result.get("selected") or {}
        lines.append(f"- selected: `{selected.get('id')}`")
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
    parser.add_argument("--format", choices=("text", "json"), default="text")
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
            )
            record_advance_result(evidence_dir, result)
        else:
            result = planned_result(
                evidence_dir,
                history_dir,
                probe_environment=args.probe_environment,
                kubectl=args.kubectl,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("version-iteration-advance: failed")
        print(f"error: {exc}")
        return 1

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_text(result)
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
