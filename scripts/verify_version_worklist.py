#!/usr/bin/env python3
"""Verify version worklist generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_version_worklist.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
WORKLIST_TOOL = "generate_version_worklist.py"
VERIFY_TOOL = "verify_version_worklist.py"
SCHEMA = "kube-actuary.version-worklist.v1"


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GENERATOR), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    json_result = run_generator("--format", "json")
    markdown_result = run_generator("--format", "markdown")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "worklist.json"
        written = run_generator("--output", str(output))
        output_written = output.is_file()

    if json_result.returncode != 0:
        errors.append(f"json worklist failed: {json_result.stderr.strip() or json_result.stdout.strip()}")
        worklist = {}
    else:
        try:
            worklist = json.loads(json_result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"json worklist must parse: {exc}")
            worklist = {}
    if markdown_result.returncode != 0:
        errors.append(f"markdown worklist failed: {markdown_result.stderr.strip() or markdown_result.stdout.strip()}")
    if "# KubeActuary Version Worklist" not in markdown_result.stdout:
        errors.append("markdown worklist missing heading")
    if written.returncode != 0 or not output_written:
        errors.append("worklist generator must write requested output file")

    summary = worklist.get("summary", {})
    versions = {version.get("version"): version for version in worklist.get("versions", []) if isinstance(version, dict)}
    if worklist.get("schemaVersion") != SCHEMA:
        errors.append("version worklist schemaVersion mismatch")
    if summary.get("openItems") != 16:
        errors.append(f"expected 16 open items, got {summary.get('openItems')!r}")
    if summary.get("captureReady") != 4:
        errors.append(f"expected 4 capture-ready items, got {summary.get('captureReady')!r}")
    if summary.get("blockedByTools") != 12:
        errors.append(f"expected 12 tool-blocked items, got {summary.get('blockedByTools')!r}")
    for expected in ("Current Baseline", "0.2.0", "0.4.4", "0.9.0"):
        if expected not in versions:
            errors.append(f"version worklist missing version: {expected}")
    if versions.get("0.2.0", {}).get("status") != "complete":
        errors.append("0.2.0 worklist should be complete")
    if versions.get("Current Baseline", {}).get("status") != "capture-ready":
        errors.append("current baseline should include capture-ready work")
    if versions.get("0.4.4", {}).get("status") != "missing-tools":
        errors.append("0.4.4 should remain missing-tools until live matrix tools are available")
    baseline_items = versions.get("Current Baseline", {}).get("openItems", [])
    if not any(item.get("captureStatus") == "tool-ready" for item in baseline_items):
        errors.append("current baseline must include a tool-ready item")
    if not any("measure_controller_resources.py" in " ".join(item.get("commands", [])) for item in baseline_items):
        errors.append("current baseline must include controller resource command")
    if not worklist.get("closureCommands"):
        errors.append("version worklist must include closure commands")

    for path in (README, README_KO, TASKBOARD):
        text = path.read_text()
        for snippet in (WORKLIST_TOOL, VERIFY_TOOL, SCHEMA):
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing version worklist detail: {snippet}")

    if errors:
        print("version-worklist: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("version-worklist: passed")
    print(f"open-items: {summary['openItems']}")
    print(f"capture-ready: {summary['captureReady']}")
    print(f"blocked-by-tools: {summary['blockedByTools']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
