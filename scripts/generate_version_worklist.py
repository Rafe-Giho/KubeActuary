#!/usr/bin/env python3
"""Generate a version-grouped worklist from the release taskboard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_live_validation_queue import build_queue  # noqa: E402
from scripts.generate_release_progress import build_progress  # noqa: E402


SCHEMA_VERSION = "kube-actuary.version-worklist.v1"


def queue_lookup(queue: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in queue.get("items", []):
        if isinstance(item, dict):
            lookup[(str(item.get("version")), str(item.get("item")))] = item
    return lookup


def work_item(item: dict[str, Any], queue_item: dict[str, Any] | None) -> dict[str, Any]:
    if queue_item is None:
        return {
            "item": item.get("item"),
            "status": item.get("status"),
            "evidence": item.get("evidence"),
            "captureStatus": "not-external-gate",
            "missingTools": [],
            "commands": [],
        }
    record = {
        "id": queue_item.get("id"),
        "item": item.get("item"),
        "status": item.get("status"),
        "evidence": item.get("evidence"),
        "kind": queue_item.get("kind"),
        "captureStatus": queue_item.get("status"),
        "missingTools": queue_item.get("missingTools", []),
        "commands": queue_item.get("commands", []),
        "nextStep": queue_item.get("nextStep"),
    }
    if queue_item.get("environmentStatus") is not None:
        record["environmentStatus"] = queue_item.get("environmentStatus")
    return record


def version_status(open_items: list[dict[str, Any]]) -> str:
    if not open_items:
        return "complete"
    if any(item.get("status") in {"DOING", "TODO"} for item in open_items):
        return "in-progress"
    if any(item.get("captureStatus") == "tool-ready" for item in open_items):
        return "capture-ready"
    if any(item.get("captureStatus") == "blocked-by-environment" for item in open_items):
        return "blocked-by-environment"
    return "missing-tools"


def summarize_versions(versions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "versions": len(versions),
        "openVersions": sum(1 for version in versions if version["status"] != "complete"),
        "openItems": sum(len(version["openItems"]) for version in versions),
        "captureReady": sum(version["summary"].get("captureReady", 0) for version in versions),
        "blockedByTools": sum(version["summary"].get("blockedByTools", 0) for version in versions),
        "blockedByEnvironment": sum(version["summary"].get("blockedByEnvironment", 0) for version in versions),
    }


def build_worklist(
    version_filters: list[str] | None = None,
    open_only: bool = False,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
) -> dict[str, Any]:
    progress = build_progress()
    queue = build_queue(probe_environment=probe_environment, kubectl=kubectl)
    queue_by_key = queue_lookup(queue)
    versions: list[dict[str, Any]] = []
    for group in progress.get("versions", []):
        version = str(group.get("version"))
        open_items = [
            work_item(item, queue_by_key.get((version, str(item.get("item")))))
            for item in group.get("openItems", [])
        ]
        capture_ready = sum(1 for item in open_items if item.get("captureStatus") == "tool-ready")
        blocked_by_tools = sum(1 for item in open_items if item.get("captureStatus") == "missing-tools")
        blocked_by_environment = sum(
            1 for item in open_items if item.get("captureStatus") == "blocked-by-environment"
        )
        versions.append(
            {
                "version": version,
                "status": version_status(open_items),
                "summary": {
                    **group.get("summary", {}),
                    "open": len(open_items),
                    "captureReady": capture_ready,
                    "blockedByTools": blocked_by_tools,
                    "blockedByEnvironment": blocked_by_environment,
                },
                "openItems": open_items,
            }
        )
    requested = set(version_filters or [])
    available = {version["version"] for version in versions}
    missing = sorted(requested - available)
    if missing:
        raise ValueError(f"unknown version: {', '.join(missing)}")
    if requested:
        versions = [version for version in versions if version["version"] in requested]
    if open_only:
        versions = [version for version in versions if version["status"] != "complete"]
    worklist = {
        "schemaVersion": SCHEMA_VERSION,
        "source": progress.get("source"),
        "releaseSuite": progress.get("releaseSuite"),
        "summary": summarize_versions(versions),
        "versions": versions,
        "closureCommands": queue.get("closureCommands", []),
    }
    if queue.get("environmentProbe"):
        worklist["environmentProbe"] = queue["environmentProbe"]
    return worklist


def render_markdown(worklist: dict[str, Any]) -> str:
    summary = worklist["summary"]
    lines = [
        "# KubeActuary Version Worklist",
        "",
        f"Schema: `{worklist['schemaVersion']}`",
        f"Source: `{worklist['source']}`",
        "",
        "## Summary",
        "",
        f"- versions: {summary['versions']}",
        f"- open versions: {summary['openVersions']}",
        f"- open items: {summary['openItems']}",
        f"- capture-ready: {summary['captureReady']}",
        f"- blocked-by-tools: {summary['blockedByTools']}",
        f"- blocked-by-environment: {summary.get('blockedByEnvironment', 0)}",
        "",
        "## Versions",
        "",
    ]
    for version in worklist["versions"]:
        counts = version["summary"]
        lines.append(
            f"- `{version['version']}` {version['status']} "
            f"done={counts.get('done', 0)} verify={counts.get('verify', 0)} open={counts.get('open', 0)}"
        )
        for item in version["openItems"]:
            lines.append(f"  - `{item['captureStatus']}` {item['item']}")
            first_command = (item.get("commands") or [None])[0]
            if item.get("environmentStatus"):
                lines.append(f"    environment: `{item['environmentStatus']}`")
            if first_command:
                lines.append(f"    command: `{first_command}`")
    lines.extend(["", "## Closure", ""])
    for command in worklist["closureCommands"]:
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary version worklist.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    parser.add_argument("--version", action="append", default=[], help="filter to a release version; repeatable")
    parser.add_argument("--open-only", action="store_true", help="include only versions with open work")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    args = parser.parse_args(argv)

    try:
        worklist = build_worklist(
            version_filters=args.version,
            open_only=args.open_only,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
        )
    except ValueError as exc:
        print("version-worklist: failed", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        rendered = json.dumps(worklist, indent=2, sort_keys=True) + "\n"
    else:
        rendered = render_markdown(worklist)

    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"version-worklist: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
