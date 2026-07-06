#!/usr/bin/env python3
"""Verify live validation queue commands stay evidence-only."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_live_validation_queue import build_queue  # noqa: E402
from scripts.verify_external_gate_command_safety import validate_command  # noqa: E402


README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
SAFE_TOOL = "verify_live_validation_queue_safety.py"
EVIDENCE_DIR = Path("evidence/live")


def queue_commands(queue: dict[str, Any]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for item in queue.get("items", []):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "unknown-item"))
        for command in item.get("commands", []):
            entries.append((item_id, str(command)))
        for command in item.get("resolvedCommands", []):
            entries.append((f"{item_id}:resolved", str(command)))
    for command in queue.get("closureCommands", []):
        entries.append(("closure", str(command)))
    for command in queue.get("resolvedClosureCommands", []):
        entries.append(("closure:resolved", str(command)))
    return entries


def main() -> int:
    errors: list[str] = []
    entries = queue_commands(build_queue()) + queue_commands(build_queue(EVIDENCE_DIR))
    kubectl_count = 0
    for source, command in entries:
        command_errors, prefix = validate_command(source, command)
        errors.extend(command_errors)
        if prefix == "kubectl":
            kubectl_count += 1

    joined = "\n".join(command for _, command in entries)
    for snippet in (
        "kubectl apply --dry-run=server",
        "scripts/build_external_evidence.py",
        "scripts/validate_live_evidence.py",
        "scripts/build_release_evidence_directory.py",
        "evidence/live/reports/",
        "evidence/live/supplemental/",
    ):
        if snippet not in joined:
            errors.append(f"queue commands missing safety snippet: {snippet}")

    for path in (README, README_KO, TASKBOARD, LIVE_VALIDATION):
        if SAFE_TOOL not in path.read_text():
            errors.append(f"{path.relative_to(ROOT)} missing {SAFE_TOOL}")

    if errors:
        print("live-validation-queue-safety: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("live-validation-queue-safety: passed")
    print(f"commands: {len(entries)}")
    print(f"kubectl: {kubectl_count}")
    print("writes: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
