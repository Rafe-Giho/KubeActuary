#!/usr/bin/env python3
"""Verify version unblock plan generation and recording."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "scripts" / "generate_version_unblock_plan.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
TEST_PLAN = ROOT / "docs" / "test-plan-v0.2.0.md"
TEST_RESULTS = ROOT / "docs" / "test-results-v0.2.0.md"
SCHEMA = "kube-actuary.version-unblock-plan.v1"


def run_plan(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(PLAN), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def parse_json(label: str, result: subprocess.CompletedProcess[str], errors: list[str]) -> dict:
    if result.returncode != 0:
        errors.append(f"{label} failed: {result.stderr.strip() or result.stdout.strip()}")
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"{label} must parse: {exc}")
        return {}


def write_prepared_queue(evidence_dir: Path) -> None:
    metadata = evidence_dir / ".kubeactuary"
    metadata.mkdir(parents=True)
    (metadata / "live-validation-queue.json").write_text(
        json.dumps(
            {
                "schemaVersion": "kube-actuary.live-validation-queue.v1",
                "source": "docs/release-taskboard.md",
                "mode": "inventory-only",
                "clusterWrites": "disabled",
                "summary": {
                    "total": 3,
                    "toolReady": 0,
                    "blockedByTools": 2,
                    "blockedByEnvironment": 1,
                    "missingTools": ["helm", "kind"],
                },
                "items": [
                    {
                        "id": "01-controller-resource-budget",
                        "version": "Current Baseline",
                        "item": "Controller resource budget",
                        "kind": "controller-resource-budget",
                        "status": "blocked-by-environment",
                        "missingTools": [],
                        "environmentStatus": "cluster-unavailable",
                        "environmentReason": "command-failed",
                        "nextStep": "start or select a disposable cluster, then rerun the probe",
                        "commands": [
                            "python3 -B scripts/capture_controller_resource_budget.py --output <kubectl-top-output.txt> --run",
                        ],
                        "resolvedCommands": [
                            (
                                "python3 -B scripts/capture_controller_resource_budget.py "
                                f"--output {evidence_dir.as_posix()}/raw/01-controller-resource-budget-kubectl-top.txt --run"
                            ),
                        ],
                        "evidenceDir": evidence_dir.as_posix(),
                    },
                    {
                        "id": "02-lightweight-cluster-smoke",
                        "version": "Current Baseline",
                        "item": "Lightweight cluster smoke",
                        "kind": "lightweight-cluster",
                        "status": "missing-tools",
                        "missingTools": ["kind"],
                        "environmentStatus": "cluster-unavailable",
                        "environmentReason": "command-failed",
                        "nextStep": "install missing tools or run on a host that has them",
                        "commands": [
                            "python3 -B scripts/run_lightweight_cluster_smoke.py --provider kind --run --output <path>",
                        ],
                        "resolvedCommands": [
                            (
                                "python3 -B scripts/run_lightweight_cluster_smoke.py --provider kind --run "
                                f"--output {evidence_dir.as_posix()}/reports/02-lightweight-cluster-smoke-lightweight-kind.json"
                            ),
                        ],
                        "evidenceDir": evidence_dir.as_posix(),
                    },
                    {
                        "id": "13-helm-chart-for-crd-and-optional-controller",
                        "version": "0.5.0",
                        "item": "Helm chart for CRD and optional controller",
                        "kind": "helm",
                        "status": "missing-tools",
                        "missingTools": ["helm"],
                        "nextStep": "install missing tools or run on a host that has them",
                        "commands": [
                            "python3 -B scripts/run_helm_smoke.py --run --output <path>",
                        ],
                        "resolvedCommands": [
                            (
                                "python3 -B scripts/run_helm_smoke.py --run "
                                f"--output {evidence_dir.as_posix()}/reports/13-helm-chart-for-crd-and-optional-controller-helm-smoke.json"
                            ),
                        ],
                        "evidenceDir": evidence_dir.as_posix(),
                    },
                ],
                "closureCommands": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def command_values(action: dict, bucket: str) -> list[str]:
    return (action.get("commands") or {}).get(bucket) or []


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        write_prepared_queue(evidence_dir)
        json_result = run_plan("--format", "json", "--evidence-dir", str(evidence_dir))
        markdown_result = run_plan("--format", "markdown", "--evidence-dir", str(evidence_dir))
        text_result = run_plan("--format", "text", "--evidence-dir", str(evidence_dir))
        filtered_kind_result = run_plan(
            "--format",
            "json",
            "--evidence-dir",
            str(evidence_dir),
            "--missing-tool",
            "kind",
        )
        filtered_environment_result = run_plan(
            "--format",
            "json",
            "--evidence-dir",
            str(evidence_dir),
            "--capture-status",
            "blocked-by-environment",
            "--environment-status",
            "cluster-unavailable",
            "--environment-reason",
            "command-failed",
        )
        record_dir = tmpdir / "metadata"
        output_path = tmpdir / "unblock.txt"
        recorded_result = run_plan(
            "--format",
            "text",
            "--evidence-dir",
            str(evidence_dir),
            "--record",
            "--record-dir",
            str(record_dir),
            "--output",
            str(output_path),
        )
        invalid_version_result = run_plan("--version", "9.9.9")

        payload = parse_json("version unblock plan", json_result, errors)
        filtered_kind = parse_json("filtered kind unblock plan", filtered_kind_result, errors)
        filtered_environment = parse_json("filtered environment unblock plan", filtered_environment_result, errors)

        if payload.get("schemaVersion") != SCHEMA:
            errors.append("unblock plan schemaVersion mismatch")
        if payload.get("sourceBlockerSchema") != "kube-actuary.version-blockers.v1":
            errors.append("unblock plan must derive from blocker ledger")
        if payload.get("sourceWorklistQueueSource") != "prepared-live-validation-queue":
            errors.append("unblock plan must use prepared evidence queue")
        if payload.get("clusterWrites") != "disabled":
            errors.append("unblock plan must keep cluster writes disabled")
        summary = payload.get("summary", {})
        if summary.get("actions") != 3:
            errors.append("unblock plan must include three fixture actions")
        if summary.get("missingToolActions") != 2 or summary.get("environmentActions") != 1:
            errors.append("unblock plan must split missing-tool and environment actions")
        actions = payload.get("actions", [])
        kind_action = next((action for action in actions if action.get("tool") == "kind"), {})
        helm_action = next((action for action in actions if action.get("tool") == "helm"), {})
        env_action = next((action for action in actions if action.get("kind") == "environment"), {})
        if "kind version" not in command_values(kind_action, "verify"):
            errors.append("kind action must include kind version verifier")
        if "helm version" not in command_values(helm_action, "verify"):
            errors.append("helm action must include helm version verifier")
        if "kubectl cluster-info --request-timeout=5s" not in command_values(env_action, "verify"):
            errors.append("environment action must include read-only cluster-info verifier")
        if env_action.get("environmentReason") != "command-failed":
            errors.append("environment action must preserve reason")
        if not any("prepare_live_evidence_directory.py" in command for command in command_values(kind_action, "refresh")):
            errors.append("missing-tool action must include queue refresh command")
        if not any("record_version_blockers.py --record" in command for command in command_values(kind_action, "record")):
            errors.append("missing-tool action must include blocker record command")
        if not any("generate_version_unblock_plan.py --record" in command for command in command_values(kind_action, "record")):
            errors.append("missing-tool action must include unblock plan record command")
        if filtered_kind.get("summary", {}).get("actions") != 1:
            errors.append("kind filter must narrow unblock plan to one action")
        if filtered_kind.get("actions", [{}])[0].get("tool") != "kind":
            errors.append("kind filter must preserve kind action")
        if filtered_environment.get("summary", {}).get("actions") != 1:
            errors.append("environment filter must narrow unblock plan to one action")
        if filtered_environment.get("actions", [{}])[0].get("kind") != "environment":
            errors.append("environment filter must preserve environment action")
        if recorded_result.returncode != 0:
            errors.append(f"recorded unblock plan failed: {recorded_result.stderr.strip() or recorded_result.stdout.strip()}")
        if not output_path.is_file():
            errors.append("recorded unblock plan must write requested output")
        record_json = record_dir / "version-unblock-plan.json"
        record_md = record_dir / "version-unblock-plan.md"
        if not record_json.is_file() or not record_md.is_file():
            errors.append("recorded unblock plan must write metadata JSON and Markdown")
        else:
            recorded_payload = json.loads(record_json.read_text())
            if recorded_payload.get("schemaVersion") != SCHEMA:
                errors.append("recorded unblock plan schema mismatch")
            if "# KubeActuary Version Unblock Plan" not in record_md.read_text():
                errors.append("recorded unblock plan Markdown title missing")
        if markdown_result.returncode != 0 or "# KubeActuary Version Unblock Plan" not in markdown_result.stdout:
            errors.append("unblock plan Markdown must render title")
        for snippet in (
            "missing-tool `kind`",
            "environment `cluster-unavailable`",
            "generate_version_unblock_plan.py --record",
        ):
            if snippet not in markdown_result.stdout:
                errors.append(f"unblock plan Markdown must include: {snippet}")
        if text_result.returncode != 0 or "actions: 3" not in text_result.stdout:
            errors.append("unblock plan text must include action count")
        if invalid_version_result.returncode == 0:
            errors.append("unblock plan must reject unknown version filters")

    required_snippets = {
        README: ("generate_version_unblock_plan.py", "kube-actuary.version-unblock-plan.v1"),
        README_KO: ("generate_version_unblock_plan.py", "kube-actuary.version-unblock-plan.v1"),
        LIVE_VALIDATION: ("generate_version_unblock_plan.py", "version-unblock-plan.json"),
        TASKBOARD: ("Version unblock plan", "verify_version_unblock_plan.py"),
        TEST_PLAN: ("verify_version_unblock_plan.py", "version unblock plan"),
        TEST_RESULTS: ("verify_version_unblock_plan.py", "version unblock plan"),
    }
    for path, snippets in required_snippets.items():
        text = path.read_text()
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} must document {snippet}")

    if errors:
        print("version-unblock-plan: failed")
        for error in errors:
            print(f"error: {error}")
        return 1
    print("version-unblock-plan: passed")
    print("actions: 3")
    print("record: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
