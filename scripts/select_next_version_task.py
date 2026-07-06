#!/usr/bin/env python3
"""Select the next local version worklist task deterministically."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_live_validation_queue import materialize_command, resolved_closure_commands  # noqa: E402
from scripts.generate_version_worklist import build_worklist  # noqa: E402


SCHEMA_VERSION = "kube-actuary.next-version-task.v1"
DEFAULT_STATUS_PRIORITY = ("tool-ready", "blocked-by-environment", "missing-tools", "not-external-gate")


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


def build_selection(
    version_filters: list[str],
    include_complete: bool,
    probe_environment: bool,
    kubectl: str,
    evidence_dir: Path | None = None,
    priority: tuple[str, ...] = DEFAULT_STATUS_PRIORITY,
) -> dict[str, Any]:
    worklist = build_worklist(
        version_filters=version_filters,
        open_only=not include_complete,
        probe_environment=probe_environment,
        kubectl=kubectl,
    )
    items = candidates(worklist)
    selected = select_candidate(items, priority)
    if selected is not None and evidence_dir is not None:
        selected = {
            **selected,
            "evidenceDir": evidence_dir.as_posix(),
            "resolvedCommands": [
                materialize_command(selected, command, evidence_dir, index + 1)
                for index, command in enumerate(selected.get("commands", []))
            ],
        }
    selection = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceWorklistSchema": worklist.get("schemaVersion"),
        "source": worklist.get("source"),
        "releaseSuite": worklist.get("releaseSuite"),
        "filters": {
            "versions": list(version_filters),
            "includeComplete": include_complete,
            "probeEnvironment": probe_environment,
            "kubectl": kubectl,
            "evidenceDir": evidence_dir.as_posix() if evidence_dir else None,
        },
        "statusPriority": list(priority),
        "summary": {
            **worklist.get("summary", {}),
            "candidateItems": len(items),
            "selected": selected is not None,
            "selectedCaptureStatus": selected.get("captureStatus") if selected else None,
        },
        "selected": selected,
        "closureCommands": worklist.get("closureCommands", []),
    }
    if worklist.get("environmentProbe"):
        selection["environmentProbe"] = worklist["environmentProbe"]
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
        f"version: {selected.get('version')}",
        f"item-id: {selected.get('id')}",
        f"item: {selected.get('item')}",
        f"capture-status: {selected.get('captureStatus')}",
        f"kind: {selected.get('kind')}",
    ]
    if selected.get("environmentStatus"):
        lines.append(f"environment-status: {selected['environmentStatus']}")
    if selected.get("missingTools"):
        lines.append(f"missing-tools: {', '.join(selected['missingTools'])}")
    if selected.get("nextStep"):
        lines.append(f"next-step: {selected['nextStep']}")
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
        if selected.get("missingTools"):
            lines.append(f"  - missing tools: `{', '.join(selected['missingTools'])}`")
        if selected.get("nextStep"):
            lines.append(f"  - next: {selected['nextStep']}")
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
