#!/usr/bin/env python3
"""Build and optionally record a version-scoped blocker ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_version_worklist import build_worklist, command_string  # noqa: E402


SCHEMA_VERSION = "kube-actuary.version-blockers.v1"
BLOCKER_STATUSES = {"blocked-by-environment", "missing-tools"}
RECORD_JSON = "version-blockers.json"
RECORD_MD = "version-blockers.md"


def ordered_unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def add_repeated(args: list[str], flag: str, values: list[Any]) -> None:
    for value in values:
        args.extend([flag, str(value)])


def base_worklist_args(filters: dict[str, Any]) -> list[str]:
    args = [
        "python3",
        "-B",
        "scripts/generate_version_worklist.py",
        "--format",
        "markdown",
        "--open-only",
    ]
    if filters.get("evidenceDir"):
        args.extend(["--evidence-dir", str(filters["evidenceDir"])])
    if filters.get("historyDir"):
        args.extend(["--history-dir", str(filters["historyDir"])])
    add_repeated(args, "--version", filters.get("versions") or [])
    return args


def base_ledger_args(filters: dict[str, Any], record: bool = False) -> list[str]:
    args = ["python3", "-B", "scripts/record_version_blockers.py"]
    if record:
        args.append("--record")
    if filters.get("evidenceDir"):
        args.extend(["--evidence-dir", str(filters["evidenceDir"])])
    if filters.get("historyDir"):
        args.extend(["--history-dir", str(filters["historyDir"])])
    add_repeated(args, "--version", filters.get("versions") or [])
    add_repeated(args, "--capture-status", filters.get("captureStatuses") or [])
    add_repeated(args, "--missing-tool", filters.get("missingTools") or [])
    add_repeated(args, "--environment-status", filters.get("environmentStatuses") or [])
    add_repeated(args, "--environment-reason", filters.get("environmentReasons") or [])
    if filters.get("probeEnvironment"):
        args.append("--probe-environment")
    if filters.get("kubectl") and filters.get("kubectl") != "kubectl":
        args.extend(["--kubectl", str(filters["kubectl"])])
    return args


def item_worklist_commands(item: dict[str, Any], filters: dict[str, Any]) -> list[str]:
    args = base_worklist_args(filters)
    if item.get("version"):
        args.extend(["--version", str(item["version"])])
    capture_status = item.get("captureStatus")
    if capture_status:
        args.extend(["--capture-status", str(capture_status)])
    if capture_status == "missing-tools" and item.get("missingTools"):
        return [
            command_string([*args, "--missing-tool", str(tool)])
            for tool in item.get("missingTools", [])
        ]
    if capture_status == "blocked-by-environment":
        if item.get("environmentStatus"):
            args.extend(["--environment-status", str(item["environmentStatus"])])
        if item.get("environmentReason"):
            args.extend(["--environment-reason", str(item["environmentReason"])])
    return [command_string(args)]


def blocker_item(version: dict[str, Any], item: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "version": version.get("version"),
        "versionStatus": version.get("status"),
        "id": item.get("id"),
        "item": item.get("item"),
        "status": item.get("status"),
        "kind": item.get("kind"),
        "captureStatus": item.get("captureStatus"),
        "missingTools": item.get("missingTools", []),
        "environmentStatus": item.get("environmentStatus"),
        "environmentReason": item.get("environmentReason"),
        "nextStep": item.get("nextStep"),
        "evidenceSummary": item.get("evidenceSummary", {}),
        "files": item.get("files", []),
        "commands": item.get("commands", []),
        "resolvedCommands": item.get("resolvedCommands", []),
    }
    if item.get("evidenceDir"):
        record["evidenceDir"] = item["evidenceDir"]
    record["worklistCommands"] = item_worklist_commands(record, filters)
    return {key: value for key, value in record.items() if value not in (None, [], {})}


def collect_blocked_items(worklist: dict[str, Any]) -> list[dict[str, Any]]:
    blocked: list[dict[str, Any]] = []
    filters = worklist.get("filters", {})
    for version in worklist.get("versions", []):
        if not isinstance(version, dict):
            continue
        for item in version.get("openItems", []):
            if isinstance(item, dict) and item.get("captureStatus") in BLOCKER_STATUSES:
                blocked.append(blocker_item(version, item, filters))
    return blocked


def affected_versions(blocked_items: list[dict[str, Any]], predicate: Any) -> list[str]:
    return ordered_unique(
        [item.get("version") for item in blocked_items if predicate(item) and item.get("version")]
    )


def summarize_missing_tools(worklist: dict[str, Any], blocked_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in worklist.get("blockers", {}).get("missingTools") or []:
        tool = item.get("tool")
        result.append(
            {
                "tool": tool,
                "items": item.get("items", 0),
                "versions": affected_versions(blocked_items, lambda blocked: tool in blocked.get("missingTools", [])),
                "worklistCommand": item.get("worklistCommand"),
            }
        )
    return result


def summarize_environment_statuses(
    worklist: dict[str, Any],
    blocked_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in worklist.get("blockers", {}).get("environment") or []:
        status = item.get("status")
        result.append(
            {
                "status": status,
                "items": item.get("items", 0),
                "versions": affected_versions(
                    blocked_items,
                    lambda blocked: (
                        blocked.get("captureStatus") == "blocked-by-environment"
                        and blocked.get("environmentStatus") == status
                    ),
                ),
                "worklistCommand": item.get("worklistCommand"),
            }
        )
    return result


def summarize_environment_reasons(
    worklist: dict[str, Any],
    blocked_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in worklist.get("blockers", {}).get("environmentReasons") or []:
        reason = item.get("reason")
        result.append(
            {
                "reason": reason,
                "items": item.get("items", 0),
                "versions": affected_versions(
                    blocked_items,
                    lambda blocked: (
                        blocked.get("captureStatus") == "blocked-by-environment"
                        and blocked.get("environmentReason") == reason
                    ),
                ),
                "worklistCommand": item.get("worklistCommand"),
            }
        )
    return result


def summarize_versions(worklist: dict[str, Any], filters: dict[str, Any]) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    for version in worklist.get("versions", []):
        if not isinstance(version, dict):
            continue
        items = [
            blocker_item(version, item, filters)
            for item in version.get("openItems", [])
            if isinstance(item, dict) and item.get("captureStatus") in BLOCKER_STATUSES
        ]
        if not items:
            continue
        summary = version.get("summary", {})
        versions.append(
            {
                "version": version.get("version"),
                "status": version.get("status"),
                "summary": {
                    "open": summary.get("open", 0),
                    "blockedByTools": summary.get("blockedByTools", 0),
                    "blockedByEnvironment": summary.get("blockedByEnvironment", 0),
                    "existingEvidenceFiles": summary.get("existingEvidenceFiles", 0),
                    "evidenceFiles": summary.get("evidenceFiles", 0),
                },
                "blockers": version.get("blockers", {}),
                "blockedItems": items,
            }
        )
    return versions


def build_ledger(
    version_filters: list[str] | None = None,
    evidence_dir: Path | None = None,
    history_dir: Path | None = None,
    probe_environment: bool = False,
    kubectl: str = "kubectl",
    capture_status_filters: list[str] | None = None,
    missing_tool_filters: list[str] | None = None,
    environment_status_filters: list[str] | None = None,
    environment_reason_filters: list[str] | None = None,
) -> dict[str, Any]:
    worklist = build_worklist(
        version_filters=version_filters,
        open_only=True,
        probe_environment=probe_environment,
        kubectl=kubectl,
        evidence_dir=evidence_dir,
        capture_status_filters=capture_status_filters,
        missing_tool_filters=missing_tool_filters,
        environment_status_filters=environment_status_filters,
        environment_reason_filters=environment_reason_filters,
        prefer_prepared_queue=bool(evidence_dir),
        history_dir=history_dir,
    )
    filters = worklist.get("filters", {})
    blocked_items = collect_blocked_items(worklist)
    versions = summarize_versions(worklist, filters)
    missing_tools = summarize_missing_tools(worklist, blocked_items)
    environment_statuses = summarize_environment_statuses(worklist, blocked_items)
    environment_reasons = summarize_environment_reasons(worklist, blocked_items)
    affected = ordered_unique([item["version"] for item in blocked_items if item.get("version")])
    summary = worklist.get("summary", {})
    ledger = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceWorklistSchema": worklist.get("schemaVersion"),
        "sourceWorklistQueueSource": worklist.get("queueSource"),
        "source": worklist.get("source"),
        "status": "blocked" if blocked_items else "clear",
        "releaseSuite": worklist.get("releaseSuite"),
        "filters": filters,
        "summary": {
            "versions": summary.get("versions", 0),
            "openVersions": summary.get("openVersions", 0),
            "openItems": summary.get("openItems", 0),
            "blockedItems": len(blocked_items),
            "blockedByTools": summary.get("blockedByTools", 0),
            "blockedByEnvironment": summary.get("blockedByEnvironment", 0),
            "missingToolBlockers": len(missing_tools),
            "environmentBlockers": len(environment_statuses),
            "environmentReasonBlockers": len(environment_reasons),
            "affectedVersions": len(affected),
            "existingEvidenceFiles": summary.get("existingEvidenceFiles", 0),
            "evidenceFiles": summary.get("evidenceFiles", 0),
        },
        "blockers": {
            "missingTools": missing_tools,
            "environment": environment_statuses,
            "environmentReasons": environment_reasons,
            "environmentNextSteps": worklist.get("blockers", {}).get("environmentNextSteps") or [],
        },
        "affectedVersions": affected,
        "versions": versions,
        "nextCommands": {
            "refreshWorklist": command_string(base_worklist_args(filters)),
            "recordBlockers": command_string(base_ledger_args(filters, record=True)),
        },
    }
    if worklist.get("evidenceDir"):
        ledger["evidenceDir"] = worklist["evidenceDir"]
    if worklist.get("historyStatus"):
        ledger["historyStatus"] = worklist["historyStatus"]
    if worklist.get("environmentProbe"):
        ledger["environmentProbe"] = worklist["environmentProbe"]
    return ledger


def filter_lines(filters: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for label, key in (
        ("versions", "versions"),
        ("capture-statuses", "captureStatuses"),
        ("missing-tools", "missingTools"),
        ("environment-statuses", "environmentStatuses"),
        ("environment-reasons", "environmentReasons"),
    ):
        values = filters.get(key) or []
        if values:
            lines.append(f"- {label}: `{', '.join(str(value) for value in values)}`")
    if filters.get("evidenceDir"):
        lines.append(f"- evidence-dir: `{filters['evidenceDir']}`")
    if filters.get("historyDir"):
        lines.append(f"- history-dir: `{filters['historyDir']}`")
    return lines


def render_markdown(ledger: dict[str, Any]) -> str:
    summary = ledger["summary"]
    lines = [
        "# KubeActuary Version Blockers",
        "",
        f"Schema: `{ledger['schemaVersion']}`",
        f"Worklist schema: `{ledger.get('sourceWorklistSchema')}`",
        f"Queue source: `{ledger.get('sourceWorklistQueueSource') or 'generated'}`",
        f"Status: `{ledger['status']}`",
        "",
        "## Summary",
        "",
        f"- open items: {summary['openItems']}",
        f"- blocked items: {summary['blockedItems']}",
        f"- blocked-by-tools: {summary['blockedByTools']}",
        f"- blocked-by-environment: {summary['blockedByEnvironment']}",
        f"- affected versions: {summary['affectedVersions']}",
        f"- evidence files: {summary['existingEvidenceFiles']}/{summary['evidenceFiles']}",
        "",
    ]
    filters = filter_lines(ledger.get("filters", {}))
    if filters:
        lines.extend(["## Filters", "", *filters, ""])
    blockers = ledger.get("blockers", {})
    if blockers.get("missingTools") or blockers.get("environment") or blockers.get("environmentReasons"):
        lines.extend(["## Blocker Groups", ""])
        for item in blockers.get("missingTools") or []:
            versions = ", ".join(item.get("versions") or ["none"])
            lines.append(f"- missing-tool: `{item['tool']}` ({item['items']} items; versions: `{versions}`)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in blockers.get("environment") or []:
            versions = ", ".join(item.get("versions") or ["none"])
            lines.append(f"- environment: `{item['status']}` ({item['items']} items; versions: `{versions}`)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in blockers.get("environmentReasons") or []:
            versions = ", ".join(item.get("versions") or ["none"])
            lines.append(f"- environment-reason: `{item['reason']}` ({item['items']} items; versions: `{versions}`)")
            if item.get("worklistCommand"):
                lines.append(f"  - worklist: `{item['worklistCommand']}`")
        for item in blockers.get("environmentNextSteps") or []:
            lines.append(f"- environment-next: {item['nextStep']} ({item['items']} items)")
        lines.append("")
    lines.extend(["## Versions", ""])
    if not ledger.get("versions"):
        lines.append("- none")
    for version in ledger.get("versions", []):
        summary = version.get("summary", {})
        lines.append(
            f"- `{version['version']}` {version['status']} "
            f"blocked={len(version.get('blockedItems', []))} open={summary.get('open', 0)}"
        )
        for item in version.get("blockedItems", []):
            lines.append(f"  - `{item['captureStatus']}` {item['item']}")
            if item.get("missingTools"):
                lines.append(f"    missing-tools: `{', '.join(item['missingTools'])}`")
            if item.get("environmentStatus"):
                lines.append(f"    environment: `{item['environmentStatus']}`")
            if item.get("environmentReason"):
                lines.append(f"    environment reason: `{item['environmentReason']}`")
            if item.get("nextStep"):
                lines.append(f"    next: {item['nextStep']}")
            evidence = item.get("evidenceSummary")
            if isinstance(evidence, dict):
                lines.append(f"    evidence: `{evidence.get('existingFiles', 0)}/{evidence.get('files', 0)}`")
            for command in item.get("worklistCommands", []):
                lines.append(f"    worklist: `{command}`")
    lines.extend(["", "## Next Local Loop", ""])
    for label, command in ledger.get("nextCommands", {}).items():
        lines.append(f"- {label}: `{command}`")
    return "\n".join(lines) + "\n"


def render_text(ledger: dict[str, Any]) -> str:
    summary = ledger["summary"]
    lines = [
        f"schema: {ledger['schemaVersion']}",
        f"queue-source: {ledger.get('sourceWorklistQueueSource') or 'generated'}",
        f"status: {ledger['status']}",
        f"open-items: {summary['openItems']}",
        f"blocked-items: {summary['blockedItems']}",
        f"blocked-by-tools: {summary['blockedByTools']}",
        f"blocked-by-environment: {summary['blockedByEnvironment']}",
        f"affected-versions: {summary['affectedVersions']}",
        f"evidence-files: {summary['existingEvidenceFiles']}/{summary['evidenceFiles']}",
    ]
    for item in ledger.get("blockers", {}).get("missingTools") or []:
        versions = ", ".join(item.get("versions") or ["none"])
        lines.append(f"missing-tool-blocker: {item['tool']} ({item['items']} items; versions: {versions})")
        if item.get("worklistCommand"):
            lines.append(f"worklist: {item['worklistCommand']}")
    for item in ledger.get("blockers", {}).get("environment") or []:
        versions = ", ".join(item.get("versions") or ["none"])
        lines.append(f"environment-blocker: {item['status']} ({item['items']} items; versions: {versions})")
        if item.get("worklistCommand"):
            lines.append(f"worklist: {item['worklistCommand']}")
    for item in ledger.get("blockers", {}).get("environmentReasons") or []:
        versions = ", ".join(item.get("versions") or ["none"])
        lines.append(f"environment-reason-blocker: {item['reason']} ({item['items']} items; versions: {versions})")
        if item.get("worklistCommand"):
            lines.append(f"worklist: {item['worklistCommand']}")
    for version in ledger.get("versions", []):
        lines.append(
            f"version: {version['version']} {version['status']} "
            f"blocked={len(version.get('blockedItems', []))}"
        )
        for item in version.get("blockedItems", []):
            lines.append(f"item: {item['version']} {item['captureStatus']} {item['item']}")
            if item.get("missingTools"):
                lines.append(f"missing-tools: {', '.join(item['missingTools'])}")
            if item.get("environmentStatus"):
                lines.append(f"environment: {item['environmentStatus']}")
            if item.get("environmentReason"):
                lines.append(f"environment-reason: {item['environmentReason']}")
            if item.get("nextStep"):
                lines.append(f"next: {item['nextStep']}")
            for command in item.get("worklistCommands", []):
                lines.append(f"worklist: {command}")
    for label, command in ledger.get("nextCommands", {}).items():
        lines.append(f"next-command: {label}: {command}")
    return "\n".join(lines) + "\n"


def render_payload(ledger: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(ledger, indent=2, sort_keys=True) + "\n"
    if fmt == "markdown":
        return render_markdown(ledger)
    return render_text(ledger)


def record_ledger(ledger: dict[str, Any], evidence_dir: Path | None, record_dir: Path | None) -> dict[str, str]:
    target = record_dir
    if target is None:
        if evidence_dir is None:
            raise ValueError("--record requires --evidence-dir or --record-dir")
        target = evidence_dir / ".kubeactuary"
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / RECORD_JSON
    md_path = target / RECORD_MD
    json_path.write_text(render_payload(ledger, "json"))
    md_path.write_text(render_payload(ledger, "markdown"))
    return {"json": json_path.as_posix(), "markdown": md_path.as_posix()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record KubeActuary version blockers.")
    parser.add_argument("--format", choices=["json", "markdown", "text"], default="json")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    parser.add_argument("--record", action="store_true", help="write version-blockers JSON and Markdown metadata")
    parser.add_argument("--record-dir", help="metadata directory for --record")
    parser.add_argument("--version", action="append", default=[], help="filter to a release version; repeatable")
    parser.add_argument("--capture-status", action="append", default=[], help="filter open items by capture status; repeatable")
    parser.add_argument("--missing-tool", action="append", default=[], help="filter open items by missing tool; repeatable")
    parser.add_argument("--environment-status", action="append", default=[], help="filter open items by environment status; repeatable")
    parser.add_argument("--environment-reason", action="append", default=[], help="filter open items by environment reason; repeatable")
    parser.add_argument("--evidence-dir", help="optional evidence directory for prepared queue and file readiness")
    parser.add_argument("--history-dir", help="optional version iteration history directory for repeated blocker context")
    parser.add_argument("--probe-environment", action="store_true", help="run read-only kubectl checks for cluster availability")
    parser.add_argument("--kubectl", default="kubectl", help="kubectl executable for --probe-environment")
    args = parser.parse_args(argv)

    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else None
    record_dir = Path(args.record_dir) if args.record_dir else None
    try:
        ledger = build_ledger(
            version_filters=args.version,
            evidence_dir=evidence_dir,
            history_dir=Path(args.history_dir) if args.history_dir else None,
            probe_environment=args.probe_environment,
            kubectl=args.kubectl,
            capture_status_filters=args.capture_status,
            missing_tool_filters=args.missing_tool,
            environment_status_filters=args.environment_status,
            environment_reason_filters=args.environment_reason,
        )
        record_paths = record_ledger(ledger, evidence_dir, record_dir) if args.record else None
    except ValueError as exc:
        print("version-blockers: failed", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        return 1

    rendered = render_payload(ledger, args.format)
    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"version-blockers: wrote {args.output}")
    if record_paths and args.output != "-":
        print(f"version-blockers: recorded {record_paths['json']}")
        print(f"version-blockers: recorded {record_paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
