#!/usr/bin/env python3
"""Generate KubeActuary release notes from local release artifacts."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def current_version() -> str:
    return (ROOT / "VERSION").read_text().strip()


def changelog_section(version: str) -> list[str]:
    lines = (ROOT / "CHANGELOG.md").read_text().splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith(f"## {version}"):
            start = index + 1
            break
    if start is None:
        return ["- No changelog section found."]

    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section.append(line)
    return trim_blank_edges(section) or ["- No changelog entries found."]


def trim_blank_edges(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def test_result_summary(version: str) -> list[str]:
    path = ROOT / "docs" / f"test-results-v{version}.md"
    if not path.is_file():
        return [f"- Test result document not found: {path.relative_to(ROOT)}"]

    lines = path.read_text().splitlines()
    summary = [f"- Evidence: `{path.relative_to(ROOT)}`"]
    seen_result = False
    seen_verification = False
    seen_tests = False
    for line in lines:
        stripped = line.strip()
        if not seen_result and stripped.startswith("Result: passed"):
            summary.append(f"- {stripped}")
            seen_result = True
        elif not seen_verification and stripped.startswith("verification: passed"):
            summary.append(f"- `{stripped}`")
            seen_verification = True
        elif not seen_tests and stripped.startswith("Ran ") and stripped.endswith("tests"):
            summary.append(f"- `{stripped}`")
            seen_tests = True
    return summary


def render_release_notes(version: str, release_date: str) -> str:
    lines = [
        f"# KubeActuary {version} Release Notes",
        "",
        f"Date: {release_date}",
        "Status: draft",
        "",
        "## Overview",
        "KubeActuary remains a local-first, evidence-carrying operations CLI for AI-assisted Kubernetes.",
        "This release does not add direct cluster write execution, an in-cluster LLM, or a controller requirement.",
        "",
        "## Changes",
        *changelog_section(version),
        "",
        "## Verification",
        *test_result_summary(version),
        f"- `python3 -B scripts/verify_release.py --version {version}`",
        "- `python3 -B -m unittest discover -s tests`",
        "- CI runs the same release verification suite on GitHub Actions.",
        "",
        "## Safety And Compatibility",
        "- Default behavior still does not execute proposed Kubernetes writes.",
        "- Evidence collectors are limited to auth, server-side dry-run, diff, local hashes, and local diagnostics.",
        "- The CLI has no external Python runtime dependency.",
        "- Controller, admission webhook, MCP wrapper, and packaging work remain future scope.",
        "",
        "## Rollback",
        "- Revert to the previous tagged CLI and CRD seed.",
        "- No cluster migration is required for the local CLI workflow.",
        "- Remove generated release artifacts if verification fails before publishing.",
        "",
    ]
    return "\n".join(lines)


def write_output(content: str, output: str) -> None:
    if output == "-":
        print(content, end="")
        return
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate KubeActuary release notes.")
    parser.add_argument("--version", default=current_version())
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    write_output(render_release_notes(args.version, args.date), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
