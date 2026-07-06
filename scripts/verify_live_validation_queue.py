#!/usr/bin/env python3
"""Verify live validation queue generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_live_validation_queue.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
QUEUE_TOOL = "generate_live_validation_queue.py"
VERIFY_TOOL = "verify_live_validation_queue.py"
SCHEMA = "kube-actuary.live-validation-queue.v1"


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
    path_result = run_generator("--format", "json", "--evidence-dir", "evidence/live")
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "queue.json"
        written = run_generator("--output", str(output))
        if written.returncode != 0 or not output.is_file():
            errors.append("queue generator must write requested output path")

    if json_result.returncode != 0:
        errors.append(f"json queue failed: {json_result.stderr.strip() or json_result.stdout.strip()}")
        queue = {}
    else:
        try:
            queue = json.loads(json_result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"json queue must parse: {exc}")
            queue = {}
    if path_result.returncode != 0:
        errors.append(f"path queue failed: {path_result.stderr.strip() or path_result.stdout.strip()}")
        path_queue = {}
    else:
        try:
            path_queue = json.loads(path_result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"path queue must parse: {exc}")
            path_queue = {}

    if markdown_result.returncode != 0:
        errors.append(f"markdown queue failed: {markdown_result.stderr.strip() or markdown_result.stdout.strip()}")
    if "# Live Validation Queue" not in markdown_result.stdout:
        errors.append("markdown queue missing heading")

    summary = queue.get("summary", {})
    items = queue.get("items", [])
    if queue.get("schemaVersion") != SCHEMA:
        errors.append("live validation queue schemaVersion mismatch")
    if queue.get("clusterWrites") != "disabled" or queue.get("mode") != "inventory-only":
        errors.append("live validation queue must stay inventory-only with disabled writes")
    if summary.get("total") != 16:
        errors.append(f"expected 16 queue items, got {summary.get('total')!r}")
    if summary.get("toolReady") != 4:
        errors.append(f"expected 4 tool-ready items, got {summary.get('toolReady')!r}")
    if len(items) != 16:
        errors.append("queue must list every external gate")
    statuses = {item.get("status") for item in items if isinstance(item, dict)}
    if statuses != {"tool-ready", "missing-tools"}:
        errors.append(f"queue must include tool-ready and missing-tools statuses: {sorted(statuses)!r}")
    for item in items:
        if not isinstance(item, dict):
            errors.append("queue item must be an object")
            continue
        if not item.get("commands"):
            errors.append(f"queue item missing commands: {item.get('id')}")
        if not isinstance(item.get("missingTools"), list):
            errors.append(f"queue item missing missingTools list: {item.get('id')}")
        if item.get("status") == "tool-ready" and item.get("missingTools"):
            errors.append(f"tool-ready item must not list missing tools: {item.get('id')}")
    joined_commands = "\n".join(
        command
        for item in items
        if isinstance(item, dict)
        for command in item.get("commands", [])
    )
    for snippet in (
        "measure_controller_resources.py --sample",
        "kubectl apply --dry-run=server",
        "run_lightweight_cluster_smoke.py --provider kind",
        "run_managed_kubernetes_smoke.py --provider eks",
    ):
        if snippet not in joined_commands:
            errors.append(f"queue missing command snippet: {snippet}")
    if not queue.get("closureCommands"):
        errors.append("queue must include closure commands")
    if path_queue.get("evidenceDir") != "evidence/live":
        errors.append("path queue must record requested evidence directory")
    path_items = path_queue.get("items", [])
    if not all(item.get("resolvedCommands") for item in path_items if isinstance(item, dict)):
        errors.append("path queue must include resolved commands for every item")
    resolved_commands = "\n".join(
        command
        for item in path_items
        if isinstance(item, dict)
        for command in item.get("resolvedCommands", [])
    )
    for placeholder in ("<path>", "<kubectl-top-output.txt>", "<external-evidence.json>"):
        if placeholder in resolved_commands:
            errors.append(f"resolved commands must not keep placeholder: {placeholder}")
    for snippet in (
        "evidence/live/reports/02-lightweight-cluster-smoke-lightweight-kind.json",
        "evidence/live/raw/01-controller-resource-budget-kubectl-top.txt",
        "evidence/live/supplemental/10-add-kubectl-explain-quality-checks-and-examples-external-3.json",
    ):
        if snippet not in resolved_commands:
            errors.append(f"resolved commands missing path: {snippet}")
    resolved_closure = "\n".join(path_queue.get("resolvedClosureCommands", []))
    if "scripts/build_release_evidence_directory.py evidence/live" not in resolved_closure:
        errors.append("path queue must include resolved release evidence directory closure")

    for path in (README, README_KO, TASKBOARD, LIVE_VALIDATION):
        text = path.read_text()
        for snippet in (QUEUE_TOOL, VERIFY_TOOL, SCHEMA):
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing live validation queue detail: {snippet}")
    if "--evidence-dir" not in LIVE_VALIDATION.read_text():
        errors.append("live validation doc missing queue evidence-dir example")

    if errors:
        print("live-validation-queue: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("live-validation-queue: passed")
    print(f"items: {summary['total']}")
    print(f"tool-ready: {summary['toolReady']}/{summary['total']}")
    print("cluster-writes: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
