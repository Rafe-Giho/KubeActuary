#!/usr/bin/env python3
"""Verify the local release taskboard stays aligned with the release suite."""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
RELEASE = ROOT / "scripts" / "verify_release.py"
ALLOWED_STATUSES = {"DONE", "VERIFY", "DOING", "TODO", "BLOCKED"}
REQUIRED_SECTIONS = (
    "## Current Baseline",
    "## v0.2.x: Alpha Stabilization",
    "## v0.3.x: CRD API Contract",
    "## v0.4.x: Low-Overhead Controller",
    "## v0.5.x: Packaging and Installation",
    "## v0.6.x: Policy and Evidence Adapters",
    "## v0.7.x: Agent and MCP Integration",
    "## v0.8.x: Optional Admission and Audit",
    "## v0.9.x: Release Candidate",
    "## v1.0.0: GA",
    "## Compatibility Policy",
)
REQUIRED_BASELINE_AREAS = (
    "Local CLI and capsule workflow",
    "v0.2 evidence collectors",
    "Controller",
    "Packaging",
    "Admission/audit",
    "Managed Kubernetes smoke",
)
VERIFY_CONTEXT_WORDS = (
    "live",
    "external",
    "provider",
    "matrix",
    "not installed",
    "required",
    "pending",
    "remaining",
    "remains",
    "blocked",
    "missing",
)


def release_check_count() -> int:
    result = subprocess.run(
        [sys.executable, "-B", str(RELEASE), "--list"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    match = re.search(r"^0\.2\.0: (\d+) checks$", result.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError("release suite list missing 0.2.0 check count")
    return int(match.group(1))


def taskboard_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 3 and cells[1] in ALLOWED_STATUSES:
            rows.append({"item": cells[0], "status": cells[1], "evidence": cells[2]})
        elif len(cells) == 4 and cells[2] in ALLOWED_STATUSES:
            rows.append({"item": cells[1], "status": cells[2], "evidence": cells[3]})
    return rows


def last_verification_count(text: str) -> int | None:
    match = re.search(r"verification: passed \((\d+) checks\)", text)
    return int(match.group(1)) if match else None


def main() -> int:
    errors: list[str] = []
    text = TASKBOARD.read_text()
    rows = taskboard_rows(text)
    statuses = Counter(row["status"] for row in rows)

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"taskboard missing section: {section}")
    for area in REQUIRED_BASELINE_AREAS:
        if f"| {area} |" not in text:
            errors.append(f"taskboard missing baseline area: {area}")

    if not rows:
        errors.append("taskboard has no parseable status rows")
    for row in rows:
        if row["status"] not in ALLOWED_STATUSES:
            errors.append(f"invalid status for {row['item']}: {row['status']}")
        if row["status"] == "DONE" and not row["evidence"]:
            errors.append(f"DONE row must include evidence: {row['item']}")
        if row["status"] in {"VERIFY", "DOING", "BLOCKED"}:
            evidence = row["evidence"].lower()
            if not any(word in evidence for word in VERIFY_CONTEXT_WORDS):
                errors.append(f"{row['status']} row must explain remaining live/external evidence: {row['item']}")

    current_checks = release_check_count()
    recorded_checks = last_verification_count(text)
    if recorded_checks != current_checks:
        errors.append(f"last verification count mismatch: taskboard={recorded_checks}, release-suite={current_checks}")

    if errors:
        print("release-taskboard: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("release-taskboard: passed")
    print(f"rows: {len(rows)}")
    print(f"done: {statuses['DONE']}")
    print(f"verify: {statuses['VERIFY']}")
    print(f"doing: {statuses['DOING']}")
    print(f"todo: {statuses['TODO']}")
    print(f"blocked: {statuses['BLOCKED']}")
    print(f"release-checks: {current_checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
