#!/usr/bin/env python3
"""Verify local milestone completion through v0.9.5."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_external_gate_plan import taskboard_rows
from scripts.verify_release import COMMON_CHECKS


TASKBOARD = ROOT / "docs" / "release-taskboard.md"
MIN_VERSION = (0, 2, 0)
TARGET_VERSION = (0, 9, 5)
TARGET_VERSION_TEXT = "0.9.5"

EXPECTED_VERSIONS = (
    "0.2.0",
    "0.2.1",
    "0.2.2",
    "0.2.3",
    "0.3.0",
    "0.3.1",
    "0.3.2",
    "0.3.3",
    "0.4.0",
    "0.4.1",
    "0.4.2",
    "0.4.3",
    "0.4.4",
    "0.5.0",
    "0.5.1",
    "0.5.2",
    "0.5.3",
    "0.5.4",
    "0.6.0",
    "0.6.1",
    "0.6.2",
    "0.6.3",
    "0.7.0",
    "0.7.1",
    "0.7.2",
    "0.7.3",
    "0.7.4",
    "0.8.0",
    "0.8.1",
    "0.8.2",
    "0.8.3",
    "0.8.4",
    "0.8.5",
    "0.9.0",
    "0.9.1",
    "0.9.2",
    "0.9.3",
    "0.9.4",
    "0.9.5",
)

REQUIRED_RELEASE_CHECKS = (
    "unit tests",
    "release taskboard",
    "release progress",
    "milestone completion",
    "version worklist",
    "version blockers",
    "version unblock plan",
    "next version task runner",
    "version iteration advance",
    "external gate plan",
    "external gate command safety",
    "crd compatibility smoke",
    "crd explain quality",
    "conformance suite",
    "controller contract",
    "controller resource budget",
    "lightweight cluster smoke",
    "helm chart",
    "krew manifest",
    "supply chain",
    "security docs",
    "api freeze",
    "docs freeze",
    "project governance",
    "mcp contract",
    "execute disabled",
    "admission webhook",
)

REQUIRED_DOCS = {
    "docs/release-taskboard.md": (
        "## v0.9.x: Release Candidate",
        "0.9.5",
        "Project governance and contribution policy",
    ),
    "docs/roadmap.md": (
        "## v0.9: Release Candidate Evidence",
        "actual provider support still requires one approved run report per provider",
    ),
    "docs/completion-audit.md": (
        "v0.9.5 Local Completion Snapshot",
        "verify_milestone_completion.py",
    ),
}

BLOCKER_REASON_TERMS = (
    "missing",
    "network-not-permitted",
    "not installed",
)


def parse_version(value: str) -> tuple[int, int, int] | None:
    try:
        parts = tuple(int(part) for part in value.split("."))
    except ValueError:
        return None
    return parts if len(parts) == 3 else None


def is_target_row(row: dict[str, str]) -> bool:
    version = row.get("version")
    if version is None:
        return False
    parsed = parse_version(version)
    if parsed is None:
        return False
    return MIN_VERSION <= parsed <= TARGET_VERSION


def main() -> int:
    errors: list[str] = []
    text = TASKBOARD.read_text()
    rows = [row for row in taskboard_rows(text) if is_target_row(row)]
    statuses = Counter(row["status"] for row in rows)
    versions = {row["version"] for row in rows if "version" in row}

    missing_versions = sorted(set(EXPECTED_VERSIONS) - versions, key=parse_version)
    if missing_versions:
        errors.append(f"missing milestone versions: {', '.join(missing_versions)}")

    if statuses["TODO"] or statuses["DOING"] or statuses["VERIFY"]:
        errors.append("milestone rows must not leave TODO, DOING, or VERIFY work")

    for row in rows:
        if row["status"] == "DONE" and not row["evidence"]:
            errors.append(f"DONE row missing verification evidence: {row['version']} {row['item']}")
        if row["status"] == "BLOCKED":
            evidence = row["evidence"].lower()
            if "blocked" not in evidence or not any(term in evidence for term in BLOCKER_REASON_TERMS):
                errors.append(f"BLOCKED row missing accepted blocker reason: {row['version']} {row['item']}")
            if "scripts/" not in row["evidence"]:
                errors.append(f"BLOCKED row must keep a local verifier command: {row['version']} {row['item']}")

    check_names = {check.name for check in COMMON_CHECKS}
    for check_name in REQUIRED_RELEASE_CHECKS:
        if check_name not in check_names:
            errors.append(f"release suite missing milestone check: {check_name}")

    for relative, snippets in REQUIRED_DOCS.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing milestone doc: {relative}")
            continue
        doc = path.read_text()
        for snippet in snippets:
            if snippet not in doc:
                errors.append(f"{relative} missing: {snippet}")

    if errors:
        print("milestone-completion: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("milestone-completion: passed")
    print(f"through-version: {TARGET_VERSION_TEXT}")
    print(f"versions: {len(versions)}")
    print(f"rows: {len(rows)}")
    print(f"done: {statuses['DONE']}")
    print(f"blocked: {statuses['BLOCKED']}")
    print("verify: 0")
    print("doing: 0")
    print("todo: 0")
    print(f"release-checks: {len(COMMON_CHECKS)}")
    print("completion-status: local-complete-with-accepted-external-blockers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
