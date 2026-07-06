#!/usr/bin/env python3
"""Compare two local version iteration packs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "kube-actuary.version-iteration-diff.v1"


def load_worklist(directory: Path) -> dict[str, Any]:
    path = directory / "worklist.json"
    if not path.is_file():
        raise ValueError(f"missing worklist: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def item_key(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("item") or "unknown-item")


def comparable_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "captureStatus": item.get("captureStatus"),
        "missingTools": item.get("missingTools", []),
        "environmentStatus": item.get("environmentStatus"),
        "environmentReason": item.get("environmentReason"),
        "evidenceSummary": item.get("evidenceSummary"),
        "commands": item.get("commands", []),
        "nextStep": item.get("nextStep"),
    }


def version_lookup(worklist: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(version.get("version")): version
        for version in worklist.get("versions", [])
        if isinstance(version, dict)
    }


def delta(after: dict[str, Any], before: dict[str, Any], key: str) -> int:
    return int(after.get(key, 0) or 0) - int(before.get(key, 0) or 0)


def compare_version(name: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    before_summary = before.get("summary", {}) if before else {}
    after_summary = after.get("summary", {}) if after else {}
    before_items = {item_key(item): item for item in before.get("openItems", [])} if before else {}
    after_items = {item_key(item): item for item in after.get("openItems", [])} if after else {}
    before_keys = set(before_items)
    after_keys = set(after_items)
    changed = sorted(
        key
        for key in before_keys & after_keys
        if comparable_item(before_items[key]) != comparable_item(after_items[key])
    )
    return {
        "version": name,
        "beforeStatus": before.get("status") if before else None,
        "afterStatus": after.get("status") if after else None,
        "statusChanged": (before.get("status") if before else None) != (after.get("status") if after else None),
        "summaryDelta": {
            "open": delta(after_summary, before_summary, "open"),
            "captureReady": delta(after_summary, before_summary, "captureReady"),
            "blockedByTools": delta(after_summary, before_summary, "blockedByTools"),
            "blockedByEnvironment": delta(after_summary, before_summary, "blockedByEnvironment"),
            "evidenceItems": delta(after_summary, before_summary, "evidenceItems"),
            "completeEvidenceItems": delta(after_summary, before_summary, "completeEvidenceItems"),
            "evidenceFiles": delta(after_summary, before_summary, "evidenceFiles"),
            "existingEvidenceFiles": delta(after_summary, before_summary, "existingEvidenceFiles"),
        },
        "addedItems": sorted(after_keys - before_keys),
        "removedItems": sorted(before_keys - after_keys),
        "changedItems": changed,
    }


def summarize(version_diffs: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "versions": len(version_diffs),
        "statusChanged": sum(1 for version in version_diffs if version["statusChanged"]),
        "openItemsDelta": sum(version["summaryDelta"]["open"] for version in version_diffs),
        "captureReadyDelta": sum(version["summaryDelta"]["captureReady"] for version in version_diffs),
        "blockedByToolsDelta": sum(version["summaryDelta"]["blockedByTools"] for version in version_diffs),
        "blockedByEnvironmentDelta": sum(
            version["summaryDelta"]["blockedByEnvironment"] for version in version_diffs
        ),
        "evidenceItemsDelta": sum(version["summaryDelta"]["evidenceItems"] for version in version_diffs),
        "completeEvidenceItemsDelta": sum(
            version["summaryDelta"]["completeEvidenceItems"] for version in version_diffs
        ),
        "evidenceFilesDelta": sum(version["summaryDelta"]["evidenceFiles"] for version in version_diffs),
        "existingEvidenceFilesDelta": sum(
            version["summaryDelta"]["existingEvidenceFiles"] for version in version_diffs
        ),
        "addedItems": sum(len(version["addedItems"]) for version in version_diffs),
        "removedItems": sum(len(version["removedItems"]) for version in version_diffs),
        "changedItems": sum(len(version["changedItems"]) for version in version_diffs),
    }


def compare_iterations(before_dir: Path, after_dir: Path) -> dict[str, Any]:
    before = load_worklist(before_dir)
    after = load_worklist(after_dir)
    before_versions = version_lookup(before)
    after_versions = version_lookup(after)
    names = sorted(set(before_versions) | set(after_versions))
    version_diffs = [
        compare_version(name, before_versions.get(name), after_versions.get(name))
        for name in names
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "before": {
            "path": before_dir.as_posix(),
            "schemaVersion": before.get("schemaVersion"),
            "summary": before.get("summary", {}),
        },
        "after": {
            "path": after_dir.as_posix(),
            "schemaVersion": after.get("schemaVersion"),
            "summary": after.get("summary", {}),
        },
        "summary": summarize(version_diffs),
        "versions": version_diffs,
    }


def render_markdown(diff: dict[str, Any]) -> str:
    summary = diff["summary"]
    lines = [
        "# KubeActuary Version Iteration Diff",
        "",
        f"Schema: `{diff['schemaVersion']}`",
        f"Before: `{diff['before']['path']}`",
        f"After: `{diff['after']['path']}`",
        "",
        "## Summary",
        "",
        f"- versions: {summary['versions']}",
        f"- status-changed: {summary['statusChanged']}",
        f"- open-items-delta: {summary['openItemsDelta']}",
        f"- capture-ready-delta: {summary['captureReadyDelta']}",
        f"- blocked-by-tools-delta: {summary['blockedByToolsDelta']}",
        f"- blocked-by-environment-delta: {summary['blockedByEnvironmentDelta']}",
        f"- existing-evidence-files-delta: {summary['existingEvidenceFilesDelta']}",
        f"- complete-evidence-items-delta: {summary['completeEvidenceItemsDelta']}",
        f"- changed-items: {summary['changedItems']}",
        "",
        "## Versions",
        "",
    ]
    for version in diff["versions"]:
        lines.append(
            f"- `{version['version']}` {version['beforeStatus']} -> {version['afterStatus']} "
            f"open={version['summaryDelta']['open']} "
            f"capture-ready={version['summaryDelta']['captureReady']} "
            f"blocked-by-environment={version['summaryDelta']['blockedByEnvironment']} "
            f"evidence-files={version['summaryDelta']['existingEvidenceFiles']}"
        )
        for item in version["changedItems"]:
            lines.append(f"  changed: `{item}`")
        for item in version["addedItems"]:
            lines.append(f"  added: `{item}`")
        for item in version["removedItems"]:
            lines.append(f"  removed: `{item}`")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two KubeActuary version iteration packs.")
    parser.add_argument("before_dir")
    parser.add_argument("after_dir")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", "-o", default="-", help="output path, or '-' for stdout")
    args = parser.parse_args(argv)

    try:
        diff = compare_iterations(Path(args.before_dir), Path(args.after_dir))
    except ValueError as exc:
        print("version-iteration-diff: failed")
        print(f"error: {exc}")
        return 1

    rendered = (
        json.dumps(diff, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else render_markdown(diff)
    )
    if args.output == "-":
        print(rendered, end="")
    else:
        Path(args.output).write_text(rendered)
        print(f"version-iteration-diff: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
