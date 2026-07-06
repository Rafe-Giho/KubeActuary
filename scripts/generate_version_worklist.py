#!/usr/bin/env python3
"""Generate a version-grouped worklist from the release taskboard."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_live_validation_queue import SCHEMA_VERSION as LIVE_QUEUE_SCHEMA  # noqa: E402
from scripts.generate_live_validation_queue import build_queue  # noqa: E402
from scripts.generate_release_progress import build_progress  # noqa: E402


SCHEMA_VERSION = "kube-actuary.version-worklist.v1"
LIVE_QUEUE_PATH = ".kubeactuary/live-validation-queue.json"
EVIDENCE_FILE_FLAGS = {
    "--sample": "sample",
    "--source": "source",
    "--output": "output",
}


def load_prepared_queue(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / LIVE_QUEUE_PATH
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: live validation queue must be a JSON object")
    if payload.get("schemaVersion") != LIVE_QUEUE_SCHEMA:
        raise ValueError(f"{path}: unsupported live-validation-queue schemaVersion: {payload.get('schemaVersion')!r}")
    payload = dict(payload)
    payload["path"] = path.as_posix()
    return payload


def worklist_queue(
    evidence_dir: Path | None,
    probe_environment: bool,
    kubectl: str,
    prefer_prepared_queue: bool = False,
) -> tuple[dict[str, Any], str]:
    if evidence_dir is not None and (not probe_environment or prefer_prepared_queue):
        prepared = load_prepared_queue(evidence_dir)
        if prepared is not None:
            return prepared, "prepared-live-validation-queue"
    return build_queue(evidence_dir=evidence_dir, probe_environment=probe_environment, kubectl=kubectl), "generated"


def queue_lookup(queue: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in queue.get("items", []):
        if isinstance(item, dict):
            lookup[(str(item.get("version")), str(item.get("item")))] = item
    return lookup


def evidence_files(item: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for command in item.get("resolvedCommands", []):
        try:
            tokens = shlex.split(command)
        except ValueError:
            continue
        for index, token in enumerate(tokens[:-1]):
            role = EVIDENCE_FILE_FLAGS.get(token)
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


def sorted_counts(counts: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"value": value, "items": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def work_item_blockers(open_items: list[dict[str, Any]]) -> dict[str, Any]:
    missing_tools = Counter(
        tool
        for item in open_items
        if item.get("captureStatus") == "missing-tools"
        for tool in item.get("missingTools", [])
    )
    environment_statuses = Counter(
        item.get("environmentStatus") or "unknown"
        for item in open_items
        if item.get("captureStatus") == "blocked-by-environment"
    )
    environment_next_steps = Counter(
        item.get("nextStep")
        for item in open_items
        if item.get("captureStatus") == "blocked-by-environment" and item.get("nextStep")
    )
    return {
        "missingTools": [
            {"tool": item["value"], "items": item["items"]}
            for item in sorted_counts(missing_tools)
        ],
        "environment": [
            {"status": item["value"], "items": item["items"]}
            for item in sorted_counts(environment_statuses)
        ],
        "environmentNextSteps": [
            {"nextStep": item["value"], "items": item["items"]}
            for item in sorted_counts(environment_next_steps)
        ],
    }


def item_matches_filters(
    item: dict[str, Any],
    capture_statuses: set[str],
    missing_tools: set[str],
    environment_statuses: set[str],
) -> bool:
    if capture_statuses and item.get("captureStatus") not in capture_statuses:
        return False
    if missing_tools and not missing_tools.intersection(item.get("missingTools", [])):
        return False
    if environment_statuses and item.get("environmentStatus") not in environment_statuses:
        return False
    return True


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
    if queue_item.get("evidenceDir") is not None:
        record["evidenceDir"] = queue_item.get("evidenceDir")
    if queue_item.get("resolvedCommands"):
        record["resolvedCommands"] = queue_item.get("resolvedCommands", [])
        files = evidence_files(record)
        record["files"] = files
        record["evidenceSummary"] = evidence_summary(files)
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
    evidence_items = [
        item
        for version in versions
        for item in version["openItems"]
        if item.get("evidenceSummary")
    ]
    return {
        "versions": len(versions),
        "openVersions": sum(1 for version in versions if version["status"] != "complete"),
        "openItems": sum(len(version["openItems"]) for version in versions),
        "captureReady": sum(version["summary"].get("captureReady", 0) for version in versions),
        "blockedByTools": sum(version["summary"].get("blockedByTools", 0) for version in versions),
        "blockedByEnvironment": sum(version["summary"].get("blockedByEnvironment", 0) for version in versions),
        "evidenceItems": len(evidence_items),
        "completeEvidenceItems": sum(1 for item in evidence_items if item["evidenceSummary"].get("complete")),
        "evidenceFiles": sum(item["evidenceSummary"].get("files", 0) for item in evidence_items),
        "existingEvidenceFiles": sum(item["evidenceSummary"].get("existingFiles", 0) for item in evidence_items),
    }


def build_worklist(
    version_filters: list[str] | None = None,
    open_only: bool = False,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
    evidence_dir: Path | None = None,
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
    prefer_prepared_queue: bool = False,
) -> dict[str, Any]:
    progress = build_progress()
    queue, queue_source = worklist_queue(evidence_dir, probe_environment, kubectl, prefer_prepared_queue)
    queue_by_key = queue_lookup(queue)
    capture_statuses = set(capture_status_filters or [])
    missing_tools = set(missing_tool_filters or [])
    environment_statuses = set(environment_status_filters or [])
    versions: list[dict[str, Any]] = []
    for group in progress.get("versions", []):
        version = str(group.get("version"))
        open_items = [
            work_item(item, queue_by_key.get((version, str(item.get("item")))))
            for item in group.get("openItems", [])
        ]
        open_items = [
            item
            for item in open_items
            if item_matches_filters(item, capture_statuses, missing_tools, environment_statuses)
        ]
        capture_ready = sum(1 for item in open_items if item.get("captureStatus") == "tool-ready")
        blocked_by_tools = sum(1 for item in open_items if item.get("captureStatus") == "missing-tools")
        blocked_by_environment = sum(
            1 for item in open_items if item.get("captureStatus") == "blocked-by-environment"
        )
        evidence_items = [item for item in open_items if item.get("evidenceSummary")]
        version_blockers = work_item_blockers(open_items)
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
                    "evidenceItems": len(evidence_items),
                    "completeEvidenceItems": sum(
                        1 for item in evidence_items if item["evidenceSummary"].get("complete")
                    ),
                    "evidenceFiles": sum(item["evidenceSummary"].get("files", 0) for item in evidence_items),
                    "existingEvidenceFiles": sum(
                        item["evidenceSummary"].get("existingFiles", 0) for item in evidence_items
                    ),
                },
                "blockers": version_blockers,
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
        "queueSource": queue_source,
        "releaseSuite": progress.get("releaseSuite"),
        "filters": {
            "versions": list(version_filters or []),
            "openOnly": open_only,
            "captureStatuses": list(capture_status_filters or []),
            "missingTools": list(missing_tool_filters or []),
            "environmentStatuses": list(environment_status_filters or []),
            "probeEnvironment": probe_environment,
            "kubectl": kubectl,
            "evidenceDir": evidence_dir.as_posix() if evidence_dir else None,
        },
        "summary": summarize_versions(versions),
        "blockers": work_item_blockers(
            [
                item
                for version in versions
                for item in version.get("openItems", [])
                if isinstance(item, dict)
            ]
        ),
        "versions": versions,
        "closureCommands": queue.get("closureCommands", []),
    }
    if queue.get("environmentProbe"):
        worklist["environmentProbe"] = queue["environmentProbe"]
    if evidence_dir is not None:
        worklist["evidenceDir"] = evidence_dir.as_posix()
        worklist["resolvedClosureCommands"] = queue.get("resolvedClosureCommands", [])
    return worklist


def render_markdown(worklist: dict[str, Any]) -> str:
    summary = worklist["summary"]
    lines = [
        "# KubeActuary Version Worklist",
        "",
        f"Schema: `{worklist['schemaVersion']}`",
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
        "",
    ]
    filters = worklist.get("filters", {})
    active_filters = [
        ("versions", filters.get("versions") or []),
        ("capture-statuses", filters.get("captureStatuses") or []),
        ("missing-tools", filters.get("missingTools") or []),
        ("environment-statuses", filters.get("environmentStatuses") or []),
    ]
    active_filters = [(name, values) for name, values in active_filters if values]
    if active_filters:
        lines.extend(["## Filters", ""])
        for name, values in active_filters:
            lines.append(f"- {name}: `{', '.join(values)}`")
        lines.append("")
    blockers = worklist.get("blockers", {})
    missing_tool_blockers = blockers.get("missingTools") or []
    environment_blockers = blockers.get("environment") or []
    environment_next_steps = blockers.get("environmentNextSteps") or []
    if missing_tool_blockers or environment_blockers:
        lines.extend(["## Blockers", ""])
        for item in missing_tool_blockers:
            lines.append(f"- missing-tool-blocker: `{item['tool']}` ({item['items']} items)")
        for item in environment_blockers:
            lines.append(f"- environment-blocker: `{item['status']}` ({item['items']} items)")
        for item in environment_next_steps:
            lines.append(f"- blocker-next-step: {item['nextStep']} ({item['items']} items)")
        lines.append("")
    lines.extend(["## Versions", ""])
    for version in worklist["versions"]:
        counts = version["summary"]
        lines.append(
            f"- `{version['version']}` {version['status']} "
            f"done={counts.get('done', 0)} verify={counts.get('verify', 0)} open={counts.get('open', 0)}"
        )
        version_blockers = version.get("blockers", {})
        version_missing = version_blockers.get("missingTools") or []
        version_environment = version_blockers.get("environment") or []
        if version_missing:
            tools = ", ".join(f"{item['tool']}:{item['items']}" for item in version_missing)
            lines.append(f"  blockers: tools=`{tools}`")
        if version_environment:
            statuses = ", ".join(f"{item['status']}:{item['items']}" for item in version_environment)
            lines.append(f"  blockers: environment=`{statuses}`")
        for item in version["openItems"]:
            lines.append(f"  - `{item['captureStatus']}` {item['item']}")
            first_command = (item.get("commands") or [None])[0]
            if item.get("environmentStatus"):
                lines.append(f"    environment: `{item['environmentStatus']}`")
            if item.get("missingTools"):
                lines.append(f"    missing tools: `{', '.join(item['missingTools'])}`")
            if item.get("nextStep"):
                lines.append(f"    next: {item['nextStep']}")
            if item.get("evidenceSummary"):
                evidence = item["evidenceSummary"]
                lines.append(f"    evidence: `{evidence.get('existingFiles', 0)}/{evidence.get('files', 0)}`")
            if first_command:
                lines.append(f"    command: `{first_command}`")
            first_resolved = (item.get("resolvedCommands") or [None])[0]
            if first_resolved:
                lines.append(f"    resolved: `{first_resolved}`")
    lines.extend(["", "## Closure", ""])
    for command in worklist.get("resolvedClosureCommands") or worklist["closureCommands"]:
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary version worklist.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    parser.add_argument("--version", action="append", default=[], help="filter to a release version; repeatable")
    parser.add_argument("--open-only", action="store_true", help="include only versions with open work")
    parser.add_argument("--capture-status", action="append", default=[], help="filter open items by capture status; repeatable")
    parser.add_argument("--missing-tool", action="append", default=[], help="filter open items by missing tool; repeatable")
    parser.add_argument("--environment-status", action="append", default=[], help="filter open items by environment status; repeatable")
    parser.add_argument("--evidence-dir", help="optional evidence directory for resolved commands and file readiness")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    args = parser.parse_args(argv)

    try:
        worklist = build_worklist(
            version_filters=args.version,
            open_only=args.open_only,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
            evidence_dir=Path(args.evidence_dir) if args.evidence_dir else None,
            capture_status_filters=args.capture_status,
            missing_tool_filters=args.missing_tool,
            environment_status_filters=args.environment_status,
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
