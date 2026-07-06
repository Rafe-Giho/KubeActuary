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
    priority: tuple[str, ...] = DEFAULT_STATUS_PRIORITY,
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
    environment_reason_filters: list[str] | None = None,
    prefer_prepared_queue: bool = False,
) -> dict[str, Any]:
    if skip_complete_evidence and evidence_dir is None:
        raise ValueError("--skip-complete-evidence requires --evidence-dir")
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
    selected = select_candidate(eligible_items, priority)
    skipped_complete_evidence = len(selectable_items) - len(eligible_items)
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
            "selected": selected is not None,
            "selectedCaptureStatus": selected.get("captureStatus") if selected else None,
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
            ]
        ) + "\n"
    lines = [
        "next-version-task: selected",
        f"queue-source: {selection.get('sourceWorklistQueueSource') or 'generated'}",
        f"version: {selected.get('version')}",
        f"item-id: {selected.get('id')}",
        f"item: {selected.get('item')}",
        f"capture-status: {selected.get('captureStatus')}",
        f"kind: {selected.get('kind')}",
    ]
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
    for command in selected.get("commands", []):
        lines.append(f"command: {command}")
    for command in selected.get("resolvedCommands", []):
        lines.append(f"resolved-command: {command}")
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
        f"- selected capture status: {summary.get('selectedCaptureStatus') or 'none'}",
        "",
        "## Selected",
        "",
    ]
    if not selected:
        lines.append("- none")
    else:
        lines.append(f"- `{selected.get('captureStatus')}` {selected.get('item')} ({selected.get('version')})")
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
        for command in selected.get("commands", []):
            lines.append(f"  - `{command}`")
        for command in selected.get("resolvedCommands", []):
            lines.append(f"  - resolved: `{command}`")
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
