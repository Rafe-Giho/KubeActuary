#!/usr/bin/env python3
"""Verify project governance, contribution, notice, and license files."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "LICENSE": (
        "MIT License",
        "KubeActuary contributors",
    ),
    "NOTICE": (
        "KubeActuary",
        "MIT License",
        "No third-party source code requiring additional NOTICE terms",
    ),
    "SECURITY.md": (
        "Reporting a Vulnerability",
        "Do not open a public issue with exploit details",
    ),
    "CONTRIBUTING.md": (
        "Safety Boundary",
        "python3 -B -m unittest discover -s tests",
        "python3 -B scripts/verify_release.py --version current",
        "Do not mark live Kubernetes, Helm, Krew, or managed-provider validation as done",
        "SECURITY.md",
        "MIT License",
    ),
    "README.md": (
        "CONTRIBUTING.md",
        "NOTICE",
    ),
    "README.ko.md": (
        "CONTRIBUTING.md",
        "NOTICE",
    ),
    "docs/release-taskboard.md": (
        "Project governance",
        "License, NOTICE, SECURITY, CONTRIBUTING",
    ),
}


def main() -> int:
    errors: list[str] = []
    for relative, snippets in FILES.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing file: {relative}")
            continue
        text = path.read_text()
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{relative} missing: {snippet}")

    if errors:
        print("project-governance: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("project-governance: passed")
    print("license: MIT")
    print("notice: present")
    print("contributing: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
