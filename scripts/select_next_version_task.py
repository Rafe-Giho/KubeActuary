#!/usr/bin/env python3
"""Select the next local version worklist task deterministically."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_live_validation_queue import materialize_command, resolved_closure_commands  # noqa: E402
from scripts.generate_version_worklist import build_worklist  # noqa: E402


SCHEMA_VERSION = "kube-actuary.next-version-task.v1"
RUNNABLE_CAPTURE_STATUS = "tool-ready"
DEFAULT_STATUS_PRIORITY = ("tool-ready", "blocked-by-environment", "missing-tools", "not-external-gate")
NEXT_TASK_FILE_FLAGS = {
    "--sample": "sample",
    "--source": "source",
    "--output": "output",
}


def candidates(worklist: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for version_index, version in enumerate(worklist.get("versions", []), start=1):
        for item_index, item in enumerate(version.get("openItems", []), start=1):
            record = {
                **item,
                "version": version.get("version"),
                "versionStatus": version.get("status"),
                "versionIndex": version_index,
                "itemIndex": item_index,
            }
            records.append(record)
    return records


def select_candidate(items: list[dict[str, Any]], priority: tuple[str, ...]) -> dict[str, Any] | None:
    for status in priority:
        for item in items:
            if item.get("captureStatus") == status:
                return item
    return items[0] if items else None


def next_task_files(selected: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for command in selected.get("resolvedCommands", []):
        try:
            tokens = shlex.split(command)
        except ValueError:
            continue
        for index, token in enumerate(tokens[:-1]):
            role = NEXT_TASK_FILE_FLAGS.get(token)
            if role is None:
                continue
            path = tokens[index + 1]
            key = (role, path)
            if key in seen:
                continue
            seen.add(key)
            files.append({"role": role, "path": path, "exists": Path(path).is_file()})
    return files


def evidence_summary(files: list[dict[str, Any]]) -> dict[str, int | bool]:
    existing = sum(1 for item in files if item["exists"])
    return {
        "files": len(files),
        "existingFiles": existing,
        "missingFiles": len(files) - existing,
        "complete": bool(files) and existing == len(files),
    }


def command_string(args: list[str]) -> str:
    return " ".join(shlex.quote(arg) for arg in args)


def selected_worklist_command(
    selected: dict[str, Any],
    filter_flag: str | None = None,
    filter_value: str | None = None,
    evidence_dir: Path | None = None,
    history_dir: Path | None = None,
) -> str:
    args = [
        "python3",
        "-B",
        "scripts/generate_version_worklist.py",
        "--format",
        "markdown",
        "--open-only",
    ]
    if evidence_dir is not None:
        args.extend(["--evidence-dir", evidence_dir.as_posix()])
    if history_dir is not None:
        args.extend(["--history-dir", history_dir.as_posix()])
    if selected.get("version"):
        args.extend(["--version", str(selected["version"])])
    if selected.get("captureStatus"):
        args.extend(["--capture-status", str(selected["captureStatus"])])
    if filter_flag is not None and filter_value is not None:
        args.extend([filter_flag, filter_value])
    return command_string(args)


def blocker_worklist_commands(
    selected: dict[str, Any],
    evidence_dir: Path | None = None,
    history_dir: Path | None = None,
) -> list[str]:
    commands: list[str] = []

    def add(filter_flag: str | None = None, filter_value: str | None = None) -> None:
        command = selected_worklist_command(selected, filter_flag, filter_value, evidence_dir, history_dir)
        if command not in commands:
            commands.append(command)

    if selected.get("environmentStatus"):
        add("--environment-status", str(selected["environmentStatus"]))
    if selected.get("environmentReason"):
        add("--environment-reason", str(selected["environmentReason"]))
    for tool in selected.get("missingTools") or []:
        add("--missing-tool", str(tool))
    if not commands:
        add()
    return commands


def blocker_message(selected: dict[str, Any]) -> str:
    missing_tools = selected.get("missingTools") or []
    if missing_tools:
        return f"missing tools: {', '.join(str(tool) for tool in missing_tools)}"
    if selected.get("environmentReason"):
        return f"environment reason: {selected['environmentReason']}"
    if selected.get("environmentStatus"):
        return f"environment status: {selected['environmentStatus']}"
    if selected.get("nextStep"):
        return str(selected["nextStep"])
    return f"capture status is {selected.get('captureStatus') or 'not-ready'}"


def annotate_selected(
    selected: dict[str, Any] | None,
    evidence_dir: Path | None = None,
    history_dir: Path | None = None,
) -> dict[str, Any] | None:
    if selected is None:
        return None
    annotated = {**selected}
    runnable = annotated.get("captureStatus") == RUNNABLE_CAPTURE_STATUS
    annotated["runnable"] = runnable
    if not runnable:
        annotated["blocker"] = {
            "captureStatus": annotated.get("captureStatus") or "not-ready",
            "message": blocker_message(annotated),
            "nextStep": annotated.get("nextStep"),
            "environmentStatus": annotated.get("environmentStatus"),
            "environmentReason": annotated.get("environmentReason"),
            "missingTools": annotated.get("missingTools") or [],
            "worklistCommands": blocker_worklist_commands(annotated, evidence_dir, history_dir),
        }
    return annotated


def materialize_item(item: dict[str, Any], evidence_dir: Path) -> dict[str, Any]:
    selected = {
        **item,
        "evidenceDir": evidence_dir.as_posix(),
        "resolvedCommands": [
            materialize_command(item, command, evidence_dir, index + 1)
            for index, command in enumerate(item.get("commands", []))
        ],
    }
    files = next_task_files(selected)
    return {**selected, "files": files, "evidenceSummary": evidence_summary(files)}


def build_selection(
    version_filters: list[str],
    include_complete: bool,
    probe_environment: bool,
    kubectl: str,
    evidence_dir: Path | None = None,
    history_dir: Path | None = None,
    skip_complete_evidence: bool = False,
    runnable_only: bool = False,
    blocked_only: bool = False,
    priority: tuple[str, ...] = DEFAULT_STATUS_PRIORITY,
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
    environment_reason_filters: list[str] | None = None,
    prefer_prepared_queue: bool = False,
) -> dict[str, Any]:
    if skip_complete_evidence and evidence_dir is None:
        raise ValueError("--skip-complete-evidence requires --evidence-dir")
    if runnable_only and blocked_only:
        raise ValueError("--runnable-only and --blocked-only are mutually exclusive")
    worklist = build_worklist(
        version_filters=version_filters,
        open_only=not include_complete,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
        environment_reason_filters=environment_reason_filters,
        prefer_prepared_queue=prefer_prepared_queue,
        history_dir=history_dir,
    )
    items = candidates(worklist)
    selectable_items = [materialize_item(item, evidence_dir) for item in items] if evidence_dir is not None else items
    if skip_complete_evidence:
        eligible_items = [
            item
            for item in selectable_items
            if item.get("evidenceSummary", {}).get("complete") is not True
        ]
    else:
        eligible_items = selectable_items
    skipped_complete_evidence = len(selectable_items) - len(eligible_items)
    eligible_before_runnable = list(eligible_items)
    if runnable_only:
        eligible_items = [
            item
            for item in eligible_items
            if item.get("captureStatus") == RUNNABLE_CAPTURE_STATUS
        ]
    if blocked_only:
        eligible_items = [
            item
            for item in eligible_items
            if item.get("captureStatus") != RUNNABLE_CAPTURE_STATUS
        ]
    selected = annotate_selected(select_candidate(eligible_items, priority), evidence_dir, history_dir)
    skipped_non_runnable = len(eligible_before_runnable) - len(eligible_items) if runnable_only else 0
    skipped_runnable = len(eligible_before_runnable) - len(eligible_items) if blocked_only else 0
    selection = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceWorklistSchema": worklist.get("schemaVersion"),
        "sourceWorklistQueueSource": worklist.get("queueSource"),
        "source": worklist.get("source"),
        "releaseSuite": worklist.get("releaseSuite"),
        "filters": {
            "versions": list(version_filters),
            "includeComplete": include_complete,
            "probeEnvironment": probe_environment,
            "kubectl": kubectl,
            "evidenceDir": evidence_dir.as_posix() if evidence_dir else None,
            "historyDir": history_dir.as_posix() if history_dir else None,
            "skipCompleteEvidence": skip_complete_evidence,
            "runnableOnly": runnable_only,
            "blockedOnly": blocked_only,
            "captureStatuses": list(capture_status_filters or []),
            "missingTools": list(missing_tool_filters or []),
            "environmentStatuses": list(environment_status_filters or []),
            "environmentReasons": list(environment_reason_filters or []),
        },
        "statusPriority": list(priority),
        "summary": {
            **worklist.get("summary", {}),
            "candidateItems": len(items),
            "eligibleItems": len(eligible_items),
            "skippedCompleteEvidence": skipped_complete_evidence,
            "skippedNonRunnable": skipped_non_runnable,
            "skippedRunnable": skipped_runnable,
            "selected": selected is not None,
            "selectedCaptureStatus": selected.get("captureStatus") if selected else None,
            "selectedRunnable": selected.get("runnable") if selected else None,
        },
        "selected": selected,
        "closureCommands": worklist.get("closureCommands", []),
    }
    if worklist.get("environmentProbe"):
        selection["environmentProbe"] = worklist["environmentProbe"]
    if worklist.get("historyStatus"):
        selection["historyStatus"] = worklist["historyStatus"]
    if evidence_dir is not None:
        selection["evidenceDir"] = evidence_dir.as_posix()
        selection["resolvedClosureCommands"] = resolved_closure_commands(evidence_dir)
    return selection


def render_text(selection: dict[str, Any]) -> str:
    selected = selection.get("selected")
    summary = selection["summary"]
    if not selected:
        return "\n".join(
            [
                "next-version-task: none",
                f"open-items: {summary.get('openItems', 0)}",
                f"candidate-items: {summary.get('candidateItems', 0)}",
                f"eligible-items: {summary.get('eligibleItems', 0)}",
                f"skipped-non-runnable: {summary.get('skippedNonRunnable', 0)}",
                f"skipped-runnable: {summary.get('skippedRunnable', 0)}",
                f"runnable-only: {str(selection.get('filters', {}).get('runnableOnly')).lower()}",
                f"blocked-only: {str(selection.get('filters', {}).get('blockedOnly')).lower()}",
            ]
        ) + "\n"
    lines = [
        "next-version-task: selected",
        f"queue-source: {selection.get('sourceWorklistQueueSource') or 'generated'}",
        f"version: {selected.get('version')}",
        f"item-id: {selected.get('id')}",
        f"item: {selected.get('item')}",
        f"capture-status: {selected.get('captureStatus')}",
        f"runnable: {str(selected.get('runnable')).lower()}",
        f"kind: {selected.get('kind')}",
    ]
    filters = selection.get("filters", {})
    if filters.get("runnableOnly") or filters.get("blockedOnly"):
        lines.append(f"runnable-only: {str(filters.get('runnableOnly')).lower()}")
        lines.append(f"blocked-only: {str(filters.get('blockedOnly')).lower()}")
    if summary.get("skippedNonRunnable", 0):
        lines.append(f"skipped-non-runnable: {summary.get('skippedNonRunnable', 0)}")
    if summary.get("skippedRunnable", 0):
        lines.append(f"skipped-runnable: {summary.get('skippedRunnable', 0)}")
    if selected.get("environmentStatus"):
        lines.append(f"environment-status: {selected['environmentStatus']}")
    if selected.get("environmentReason"):
        lines.append(f"environment-reason: {selected['environmentReason']}")
    if selected.get("missingTools"):
        lines.append(f"missing-tools: {', '.join(selected['missingTools'])}")
    if selected.get("nextStep"):
        lines.append(f"next-step: {selected['nextStep']}")
    if selected.get("evidenceSummary"):
        evidence = selected["evidenceSummary"]
        lines.append(f"evidence-files: {evidence.get('existingFiles', 0)}/{evidence.get('files', 0)}")
    history_context = selected.get("historyContext")
    if isinstance(history_context, dict):
        streak = history_context.get("latestBlockerStreak", {})
        action = history_context.get("latestBlockerAction", {})
        if isinstance(streak, dict):
            lines.append(f"history-blocker-streak: {streak.get('streak')}")
            lines.append(f"history-blocker-status: {streak.get('status')}")
            lines.append(f"history-latest-run-id: {history_context.get('latestRunId')}")
        if isinstance(action, dict):
            lines.append(f"history-blocker-action: {action.get('action')}")
            lines.append(f"history-blocker-retry-recommended: {str(action.get('retryRecommended')).lower()}")
            if action.get("nextStep"):
                lines.append(f"history-blocker-next-step: {action.get('nextStep')}")
    blocker = selected.get("blocker")
    if isinstance(blocker, dict):
        lines.append(f"blocker: {blocker.get('message')}")
        for command in blocker.get("worklistCommands") or []:
            lines.append(f"blocker-worklist: {command}")
    command_label = "command" if selected.get("runnable") else "blocked-command"
    resolved_label = "resolved-command" if selected.get("runnable") else "blocked-resolved-command"
    for command in selected.get("commands", []):
        lines.append(f"{command_label}: {command}")
    for command in selected.get("resolvedCommands", []):
        lines.append(f"{resolved_label}: {command}")
    return "\n".join(lines) + "\n"


def render_markdown(selection: dict[str, Any]) -> str:
    selected = selection.get("selected")
    summary = selection["summary"]
    lines = [
        "# KubeActuary Next Version Task",
        "",
        f"Schema: `{selection['schemaVersion']}`",
        f"Source: `{selection['source']}`",
        f"Queue source: `{selection.get('sourceWorklistQueueSource') or 'generated'}`",
        "",
        "## Summary",
        "",
        f"- open items: {summary.get('openItems', 0)}",
        f"- candidate items: {summary.get('candidateItems', 0)}",
        f"- eligible items: {summary.get('eligibleItems', 0)}",
        f"- skipped non-runnable: {summary.get('skippedNonRunnable', 0)}",
        f"- skipped runnable: {summary.get('skippedRunnable', 0)}",
        f"- selected capture status: {summary.get('selectedCaptureStatus') or 'none'}",
        "",
        "## Selected",
        "",
    ]
    if not selected:
        lines.append("- none")
    else:
        lines.append(f"- `{selected.get('captureStatus')}` {selected.get('item')} ({selected.get('version')})")
        lines.append(f"  - runnable: `{str(selected.get('runnable')).lower()}`")
        if selected.get("environmentStatus"):
            lines.append(f"  - environment: `{selected['environmentStatus']}`")
        if selected.get("environmentReason"):
            lines.append(f"  - environment reason: `{selected['environmentReason']}`")
        if selected.get("missingTools"):
            lines.append(f"  - missing tools: `{', '.join(selected['missingTools'])}`")
        if selected.get("nextStep"):
            lines.append(f"  - next: {selected['nextStep']}")
        if selected.get("evidenceSummary"):
            evidence = selected["evidenceSummary"]
            lines.append(f"  - evidence files: `{evidence.get('existingFiles', 0)}/{evidence.get('files', 0)}`")
        history_context = selected.get("historyContext")
        if isinstance(history_context, dict):
            streak = history_context.get("latestBlockerStreak", {})
            action = history_context.get("latestBlockerAction", {})
            if isinstance(streak, dict):
                lines.append(
                    f"  - history: `{streak.get('status')}` streak={streak.get('streak')} "
                    f"latest=`{history_context.get('latestRunId')}`"
                )
            if isinstance(action, dict):
                lines.append(f"  - history action: `{action.get('action')}`")
                lines.append(f"  - history retry: `{str(action.get('retryRecommended')).lower()}`")
                if action.get("nextStep"):
                    lines.append(f"  - history next: {action.get('nextStep')}")
        blocker = selected.get("blocker")
        if isinstance(blocker, dict):
            lines.append(f"  - blocker: {blocker.get('message')}")
            for command in blocker.get("worklistCommands") or []:
                lines.append(f"  - blocker worklist: `{command}`")
        command_label = "command" if selected.get("runnable") else "blocked command"
        resolved_label = "resolved" if selected.get("runnable") else "blocked resolved"
        for command in selected.get("commands", []):
            lines.append(f"  - {command_label}: `{command}`")
        for command in selected.get("resolvedCommands", []):
            lines.append(f"  - {resolved_label}: `{command}`")
    if selection.get("resolvedClosureCommands"):
        lines.extend(["", "## Resolved Closure", ""])
        for command in selection["resolvedClosureCommands"]:
            lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select the next KubeActuary version worklist task.")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    parser.add_argument("--version", action="append", default=[], help="filter to a release version; repeatable")
    parser.add_argument("--include-complete", action="store_true", help="include complete versions in the search scope")
    parser.add_argument("--evidence-dir", help="optional evidence directory for deterministic command paths")
    parser.add_argument("--history-dir", help="optional version iteration history directory for repeated blocker context")
    parser.add_argument("--runnable-only", action="store_true", help="select only tool-ready tasks and report none if all candidates are blocked")
    parser.add_argument("--blocked-only", action="store_true", help="select only non-tool-ready tasks and report none if all candidates are runnable")
    parser.add_argument("--capture-status", action="append", default=[], help="filter open items by capture status; repeatable")
    parser.add_argument("--missing-tool", action="append", default=[], help="filter open items by missing tool; repeatable")
    parser.add_argument("--environment-status", action="append", default=[], help="filter open items by environment status; repeatable")
    parser.add_argument("--environment-reason", action="append", default=[], help="filter open items by environment reason; repeatable")
    parser.add_argument(
        "--skip-complete-evidence",
        action="store_true",
        help="with --evidence-dir, skip tasks whose resolved evidence files already exist",
    )
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    args = parser.parse_args(argv)

    try:
        selection = build_selection(
            version_filters=args.version,
            include_complete=args.include_complete,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
            evidence_dir=Path(args.evidence_dir) if args.evidence_dir else None,
            history_dir=Path(args.history_dir) if args.history_dir else None,
            skip_complete_evidence=args.skip_complete_evidence,
            runnable_only=args.runnable_only,
            blocked_only=args.blocked_only,
            capture_status_filters=args.capture_status,
            missing_tool_filters=args.missing_tool,
            environment_status_filters=args.environment_status,
            environment_reason_filters=args.environment_reason,
        )
    except ValueError as exc:
        print("next-version-task: failed", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        rendered = json.dumps(selection, indent=2, sort_keys=True) + "\n"
    elif args.format == "markdown":
        rendered = render_markdown(selection)
    else:
        rendered = render_text(selection)

    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"next-version-task: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
