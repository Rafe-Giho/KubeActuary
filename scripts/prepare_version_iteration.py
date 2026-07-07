#!/usr/bin/env python3
"""Prepare a local version iteration pack from the release worklist."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_version_worklist import build_worklist, render_markdown  # noqa: E402
from scripts.inspect_release_evidence_directory import (  # noqa: E402
    load_next_unblock_action,
    load_next_unblock_action_run,
)


SCHEMA_VERSION = "kube-actuary.version-iteration.v1"
NEXT_UNBLOCK_METADATA_KEYS = ("nextUnblockAction", "nextUnblockActionRun")


def slug(value: str) -> str:
    lowered = value.lower().replace(".", "-")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or "version"


def iteration_record(version: dict[str, Any], worklist: dict[str, Any]) -> dict[str, Any]:
    record = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceWorklistSchema": worklist.get("schemaVersion"),
        "sourceWorklistQueueSource": worklist.get("queueSource"),
        "source": worklist.get("source"),
        "releaseSuite": worklist.get("releaseSuite"),
        "filters": worklist.get("filters", {}),
        "version": version.get("version"),
        "status": version.get("status"),
        "summary": version.get("summary", {}),
        "blockers": version.get("blockers", {}),
        "openItems": version.get("openItems", []),
        "closureCommands": worklist.get("closureCommands", []),
    }
    if worklist.get("evidenceDir"):
        record["evidenceDir"] = worklist["evidenceDir"]
    if worklist.get("resolvedClosureCommands"):
        record["resolvedClosureCommands"] = worklist["resolvedClosureCommands"]
    if worklist.get("environmentProbe"):
        record["environmentProbe"] = worklist["environmentProbe"]
    for key in NEXT_UNBLOCK_METADATA_KEYS:
        if worklist.get(key):
            record[key] = worklist[key]
    return record


def attach_next_unblock_metadata(worklist: dict[str, Any], evidence_dir: Path | None) -> None:
    if evidence_dir is None:
        return
    next_unblock_action = load_next_unblock_action(evidence_dir)
    if next_unblock_action is not None:
        worklist["nextUnblockAction"] = next_unblock_action
    next_unblock_action_run = load_next_unblock_action_run(evidence_dir)
    if next_unblock_action_run is not None:
        worklist["nextUnblockActionRun"] = next_unblock_action_run


def render_next_unblock_sections(record: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    action = record.get("nextUnblockAction")
    if isinstance(action, dict):
        selected = action.get("selected") if isinstance(action.get("selected"), dict) else {}
        lines.extend(["## Next Unblock Action", ""])
        if selected:
            lines.append(
                f"- `{selected.get('id')}` {selected.get('kind')} "
                f"`{selected.get('target')}` ({selected.get('items', 0)} items)"
            )
            if selected.get("nextStep"):
                lines.append(f"  next: {selected.get('nextStep')}")
            commands = selected.get("commands") if isinstance(selected.get("commands"), dict) else {}
            for command in commands.get("verify", []) or []:
                lines.append(f"  verify: `{command}`")
        else:
            lines.append("- none")
        lines.append("")
    action_run = record.get("nextUnblockActionRun")
    if isinstance(action_run, dict):
        selected = action_run.get("selected") if isinstance(action_run.get("selected"), dict) else {}
        summary = action_run.get("summary") if isinstance(action_run.get("summary"), dict) else {}
        failure = action_run.get("failure") if isinstance(action_run.get("failure"), dict) else {}
        lines.extend(["## Next Unblock Action Run", ""])
        lines.append(f"- status: `{action_run.get('status')}`")
        lines.append(f"- mode: `{action_run.get('mode')}`")
        if selected.get("id"):
            lines.append(f"- selected: `{selected.get('id')}` target=`{selected.get('target')}`")
        if summary:
            lines.append(
                f"- commands: {summary.get('commands', 0)} "
                f"ran={summary.get('ran', 0)} failed={summary.get('failed', 0)}"
            )
        if failure.get("message"):
            lines.append(f"- blocker: `{failure.get('message')}`")
        lines.append("")
    return lines


def render_iteration(record: dict[str, Any]) -> str:
    summary = record["summary"]
    lines = [
        f"# KubeActuary Version Iteration: {record['version']}",
        "",
        f"Schema: `{record['schemaVersion']}`",
        f"Source: `{record['source']}`",
        f"Queue source: `{record.get('sourceWorklistQueueSource') or 'generated'}`",
        f"Status: `{record['status']}`",
        "",
        "## Summary",
        "",
        f"- done: {summary.get('done', 0)}",
        f"- verify: {summary.get('verify', 0)}",
        f"- open: {summary.get('open', 0)}",
        f"- capture-ready: {summary.get('captureReady', 0)}",
        f"- blocked-by-tools: {summary.get('blockedByTools', 0)}",
        f"- blocked-by-environment: {summary.get('blockedByEnvironment', 0)}",
        f"- evidence files: {summary.get('existingEvidenceFiles', 0)}/{summary.get('evidenceFiles', 0)}",
        "",
    ]
    blockers = record.get("blockers", {})
    missing_tool_blockers = blockers.get("missingTools") or []
    environment_blockers = blockers.get("environment") or []
    environment_reason_blockers = blockers.get("environmentReasons") or []
    environment_next_steps = blockers.get("environmentNextSteps") or []
    if missing_tool_blockers or environment_blockers or environment_reason_blockers:
        lines.extend(["## Blockers", ""])
        for item in missing_tool_blockers:
            lines.append(f"- missing-tool-blocker: `{item['tool']}` ({item['items']} items)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in environment_blockers:
            lines.append(f"- environment-blocker: `{item['status']}` ({item['items']} items)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in environment_reason_blockers:
            lines.append(f"- environment-reason-blocker: `{item['reason']}` ({item['items']} items)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in environment_next_steps:
            lines.append(f"- blocker-next-step: {item['nextStep']} ({item['items']} items)")
        lines.append("")
    lines.extend(render_next_unblock_sections(record))
    lines.extend(["## Open Items", ""])
    if not record["openItems"]:
        lines.append("- none")
    for item in record["openItems"]:
        lines.append(f"- `{item.get('captureStatus')}` {item.get('item')}")
        if item.get("missingTools"):
            lines.append(f"  missing-tools: `{', '.join(item['missingTools'])}`")
        if item.get("environmentStatus"):
            lines.append(f"  environment: `{item['environmentStatus']}`")
        if item.get("environmentReason"):
            lines.append(f"  environment reason: `{item['environmentReason']}`")
        if item.get("nextStep"):
            lines.append(f"  next: {item['nextStep']}")
        if item.get("evidenceSummary"):
            evidence = item["evidenceSummary"]
            lines.append(f"  evidence: `{evidence.get('existingFiles', 0)}/{evidence.get('files', 0)}`")
        for command in item.get("commands", []):
            lines.append(f"  command: `{command}`")
        for command in item.get("resolvedCommands", []):
            lines.append(f"  resolved: `{command}`")
    lines.extend(["", "## Closure", ""])
    for command in record.get("resolvedClosureCommands") or record["closureCommands"]:
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def render_index(worklist: dict[str, Any]) -> str:
    summary = worklist["summary"]
    lines = [
        "# KubeActuary Version Iterations",
        "",
        f"Schema: `{SCHEMA_VERSION}`",
        f"Worklist schema: `{worklist['schemaVersion']}`",
        f"Source: `{worklist['source']}`",
        f"Queue source: `{worklist.get('queueSource', 'generated')}`",
        "",
        "## Summary",
        "",
        f"- versions: {summary['versions']}",
        f"- open versions: {summary['openVersions']}",
        f"- open items: {summary['openItems']}",
        f"- capture-ready: {summary['captureReady']}",
        f"- blocked-by-tools: {summary['blockedByTools']}",
        f"- blocked-by-environment: {summary.get('blockedByEnvironment', 0)}",
        f"- evidence files: {summary.get('existingEvidenceFiles', 0)}/{summary.get('evidenceFiles', 0)}",
        "",
    ]
    filters = worklist.get("filters", {})
    active_filters = [
        ("versions", filters.get("versions") or []),
        ("capture-statuses", filters.get("captureStatuses") or []),
        ("missing-tools", filters.get("missingTools") or []),
        ("environment-statuses", filters.get("environmentStatuses") or []),
        ("environment-reasons", filters.get("environmentReasons") or []),
    ]
    active_filters = [(name, values) for name, values in active_filters if values]
    if active_filters:
        lines.extend(["## Filters", ""])
        for name, values in active_filters:
            lines.append(f"- {name}: `{', '.join(values)}`")
        lines.append("")
    lines.extend(render_next_unblock_sections(worklist))
    lines.extend(["## Versions", ""])
    for version in worklist["versions"]:
        name = str(version["version"])
        lines.append(f"- [{name}](versions/{slug(name)}.md) `{version['status']}`")
    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def prepare_iteration_pack(
    output_dir: Path,
    version_filters: list[str],
    open_only: bool,
    probe_environment: bool,
    kubectl: str,
    evidence_dir: Path | None = None,
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
    environment_reason_filters: list[str] | None = None,
    prefer_prepared_queue: bool = False,
) -> dict[str, Any]:
    worklist = build_worklist(
        version_filters=version_filters,
        open_only=open_only,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
        environment_reason_filters=environment_reason_filters,
        prefer_prepared_queue=prefer_prepared_queue,
    )
    attach_next_unblock_metadata(worklist, evidence_dir)
    versions_dir = output_dir / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "worklist.json", worklist)
    (output_dir / "worklist.md").write_text(render_markdown(worklist))
    (output_dir / "README.md").write_text(render_index(worklist))

    for version in worklist["versions"]:
        record = iteration_record(version, worklist)
        version_slug = slug(str(version["version"]))
        write_json(versions_dir / f"{version_slug}.json", record)
        (versions_dir / f"{version_slug}.md").write_text(render_iteration(record))
    return worklist


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare local KubeActuary version iteration files.")
    parser.add_argument("output_dir", help="directory to write the iteration pack")
    parser.add_argument("--version", action="append", default=[], help="filter to a release version; repeatable")
    parser.add_argument("--open-only", action="store_true", help="include only versions with open work")
    parser.add_argument("--capture-status", action="append", default=[], help="filter open items by capture status; repeatable")
    parser.add_argument("--missing-tool", action="append", default=[], help="filter open items by missing tool; repeatable")
    parser.add_argument("--environment-status", action="append", default=[], help="filter open items by environment status; repeatable")
    parser.add_argument("--environment-reason", action="append", default=[], help="filter open items by environment reason; repeatable")
    parser.add_argument("--evidence-dir", help="optional evidence directory for resolved commands and file readiness")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    args = parser.parse_args(argv)

    try:
        worklist = prepare_iteration_pack(
            Path(args.output_dir),
            version_filters=args.version,
            open_only=args.open_only,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
            evidence_dir=Path(args.evidence_dir) if args.evidence_dir else None,
            capture_status_filters=args.capture_status,
            missing_tool_filters=args.missing_tool,
            environment_status_filters=args.environment_status,
            environment_reason_filters=args.environment_reason,
        )
    except ValueError as exc:
        print("version-iteration: failed")
        print(f"error: {exc}")
        return 1

    summary = worklist["summary"]
    print(f"version-iteration: wrote {args.output_dir}")
    print(f"versions: {summary['versions']}")
    print(f"open-items: {summary['openItems']}")
    print(f"capture-ready: {summary['captureReady']}")
    print(f"blocked-by-tools: {summary['blockedByTools']}")
    print(f"blocked-by-environment: {summary.get('blockedByEnvironment', 0)}")
    print(f"evidence-files: {summary.get('existingEvidenceFiles', 0)}/{summary.get('evidenceFiles', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
