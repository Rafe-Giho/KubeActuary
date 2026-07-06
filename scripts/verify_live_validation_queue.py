#!/usr/bin/env python3
"""Verify live validation queue generation."""

from __future__ import annotations

import json
import os
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


def run_generator(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GENERATOR), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_tool_dir(path: Path, cluster_ok: bool) -> dict[str, str]:
    path.mkdir()
    for tool in ("kind", "minikube", "microk8s", "k3s", "helm", "kubectl-krew", "aws", "gcloud", "az"):
        executable = path / tool
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
    kubectl = path / "kubectl"
    cluster_exit = 0 if cluster_ok else 1
    kubectl.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['version']:\n"
        "    print('Client Version: fake')\n"
        "    raise SystemExit(0)\n"
        "if args[:1] == ['cluster-info']:\n"
        f"    if {cluster_exit} != 0:\n"
        "        print('connection refused from fake kubectl', file=sys.stderr)\n"
        f"    raise SystemExit({cluster_exit})\n"
        "raise SystemExit(0)\n"
    )
    kubectl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', '')}"
    return env


def main() -> int:
    errors: list[str] = []
    json_result = run_generator("--format", "json")
    markdown_result = run_generator("--format", "markdown")
    path_result = run_generator("--format", "json", "--evidence-dir", "evidence/live")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        output = tmpdir / "queue.json"
        written = run_generator("--output", str(output))
        if written.returncode != 0 or not output.is_file():
            errors.append("queue generator must write requested output path")
        probe_env = fake_tool_dir(tmpdir / "tools", cluster_ok=False)
        probe_result = run_generator("--format", "json", "--probe-environment", env=probe_env)
        probe_markdown_result = run_generator("--format", "markdown", "--probe-environment", env=probe_env)

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
    if probe_result.returncode != 0:
        errors.append(f"probe queue failed: {probe_result.stderr.strip() or probe_result.stdout.strip()}")
        probe_queue = {}
    else:
        try:
            probe_queue = json.loads(probe_result.stdout)
        except json.JSONDecodeError as exc:
            errors.append(f"probe queue must parse: {exc}")
            probe_queue = {}

    if markdown_result.returncode != 0:
        errors.append(f"markdown queue failed: {markdown_result.stderr.strip() or markdown_result.stdout.strip()}")
    if "# Live Validation Queue" not in markdown_result.stdout:
        errors.append("markdown queue missing heading")
    if probe_markdown_result.returncode != 0:
        errors.append(f"probe markdown queue failed: {probe_markdown_result.stderr.strip() or probe_markdown_result.stdout.strip()}")
    elif "Environment reason: `connection-refused`" not in probe_markdown_result.stdout:
        errors.append("probe markdown queue must show environment reason")

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
    if summary.get("blockedByEnvironment") != 0:
        errors.append("default queue must not probe environment blockers")
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
        "capture_controller_resource_budget.py --output",
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

    probe_summary = probe_queue.get("summary", {})
    probe_items = probe_queue.get("items", [])
    probe_statuses = {item.get("status") for item in probe_items if isinstance(item, dict)}
    if probe_queue.get("mode") != "inventory-plus-environment-probe":
        errors.append("probe queue must record environment-probe mode")
    if probe_queue.get("environmentProbe", {}).get("clusterAccess") != "unavailable":
        errors.append("probe queue must report unavailable cluster access")
    if probe_queue.get("environmentProbe", {}).get("reason") != "connection-refused":
        errors.append("probe queue must report stable unavailable-cluster reason")
    probe_checks = probe_queue.get("environmentProbe", {}).get("checks", [])
    cluster_check = next(
        (item for item in probe_checks if isinstance(item, dict) and item.get("name") == "cluster-info"),
        {},
    )
    if cluster_check.get("reason") != "connection-refused":
        errors.append("probe queue must preserve failed check reason")
    if probe_summary.get("blockedByTools") != 0:
        errors.append("fake all-tools probe should not be blocked by missing tools")
    if probe_summary.get("blockedByEnvironment") != 14:
        errors.append(f"expected 14 environment-blocked items, got {probe_summary.get('blockedByEnvironment')!r}")
    if probe_summary.get("toolReady") != 2 or "blocked-by-environment" not in probe_statuses:
        errors.append("probe queue must leave only non-cluster Krew items tool-ready")
    if not any(item.get("environmentStatus") == "cluster-unavailable" for item in probe_items if isinstance(item, dict)):
        errors.append("probe queue must annotate cluster-unavailable items")
    if not any(item.get("environmentReason") == "connection-refused" for item in probe_items if isinstance(item, dict)):
        errors.append("probe queue must annotate environment reason on blocked items")

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
