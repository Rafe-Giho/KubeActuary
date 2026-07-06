#!/usr/bin/env python3
"""Verify version blocker ledger generation and recording."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLOCKERS = ROOT / "scripts" / "record_version_blockers.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
TEST_PLAN = ROOT / "docs" / "test-plan-v0.2.0.md"
TEST_RESULTS = ROOT / "docs" / "test-results-v0.2.0.md"
SCHEMA = "kube-actuary.version-blockers.v1"


def run_blockers(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(BLOCKERS), *args],
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
                    "missingTools": ["helm", "kind", "minikube"],
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
                        "missingTools": ["kind", "minikube"],
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
                        "environmentStatus": "cluster-unavailable",
                        "environmentReason": "command-failed",
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


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        write_prepared_queue(evidence_dir)
        json_result = run_blockers("--format", "json", "--evidence-dir", str(evidence_dir))
        markdown_result = run_blockers("--format", "markdown", "--evidence-dir", str(evidence_dir))
        text_result = run_blockers("--format", "text", "--evidence-dir", str(evidence_dir))
        filtered_kind_result = run_blockers(
            "--format",
            "json",
            "--evidence-dir",
            str(evidence_dir),
            "--capture-status",
            "missing-tools",
            "--missing-tool",
            "kind",
        )
        filtered_environment_result = run_blockers(
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
        output_path = tmpdir / "blockers.txt"
        recorded_result = run_blockers(
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
        invalid_version_result = run_blockers("--version", "9.9.9")

        payload = parse_json("version blocker ledger", json_result, errors)
        filtered_kind = parse_json("filtered kind ledger", filtered_kind_result, errors)
        filtered_environment = parse_json("filtered environment ledger", filtered_environment_result, errors)

        if payload.get("schemaVersion") != SCHEMA:
            errors.append("ledger schemaVersion mismatch")
        if payload.get("sourceWorklistQueueSource") != "prepared-live-validation-queue":
            errors.append("ledger must use prepared evidence queue")
        if payload.get("status") != "blocked":
            errors.append("ledger must report blocked status for fixture blockers")
        summary = payload.get("summary", {})
        if summary.get("blockedItems") != 3:
            errors.append("ledger must count three blocked fixture items")
        if summary.get("blockedByTools") != 2 or summary.get("blockedByEnvironment") != 1:
            errors.append("ledger must split missing-tool and environment blockers")
        missing_tools = payload.get("blockers", {}).get("missingTools", [])
        if not any(item.get("tool") == "kind" and "Current Baseline" in item.get("versions", []) for item in missing_tools):
            errors.append("ledger must include kind affected version")
        if not any(item.get("tool") == "helm" and "0.5.0" in item.get("versions", []) for item in missing_tools):
            errors.append("ledger must include helm affected version")
        environment = payload.get("blockers", {}).get("environment", [])
        if not any(item.get("status") == "cluster-unavailable" for item in environment):
            errors.append("ledger must include environment blocker")
        if any(item.get("versions") != ["Current Baseline"] for item in environment):
            errors.append("environment blocker affected versions must exclude missing-tool-only items")
        environment_reasons = payload.get("blockers", {}).get("environmentReasons", [])
        if not any(item.get("reason") == "command-failed" for item in environment_reasons):
            errors.append("ledger must include environment reason blocker")
        if any(item.get("versions") != ["Current Baseline"] for item in environment_reasons):
            errors.append("environment reason affected versions must exclude missing-tool-only items")
        next_commands = payload.get("nextCommands", {})
        if "record_version_blockers.py" not in next_commands.get("recordBlockers", ""):
            errors.append("ledger must include record blocker next command")
        if "generate_version_worklist.py" not in next_commands.get("refreshWorklist", ""):
            errors.append("ledger must include refresh worklist next command")
        versions = payload.get("versions", [])
        if not any(version.get("version") == "Current Baseline" for version in versions):
            errors.append("ledger must preserve version grouping")
        baseline = next((version for version in versions if version.get("version") == "Current Baseline"), {})
        if len(baseline.get("blockedItems", [])) != 2:
            errors.append("baseline ledger must include two blocked items")
        if not any(
            "--environment-status cluster-unavailable" in " ".join(item.get("worklistCommands", []))
            for item in baseline.get("blockedItems", [])
        ):
            errors.append("environment item must include filtered worklist command")
        if filtered_kind.get("summary", {}).get("blockedItems") != 1:
            errors.append("kind filter must narrow ledger to one blocker")
        if filtered_kind.get("blockers", {}).get("missingTools", [{}])[0].get("tool") != "kind":
            errors.append("kind filter must preserve kind blocker group")
        if filtered_environment.get("summary", {}).get("blockedItems") != 1:
            errors.append("environment filter must narrow ledger to one blocker")
        if recorded_result.returncode != 0:
            errors.append(f"recorded blocker ledger failed: {recorded_result.stderr.strip() or recorded_result.stdout.strip()}")
        if not output_path.is_file():
            errors.append("recorded blocker ledger must write requested output")
        record_json = record_dir / "version-blockers.json"
        record_md = record_dir / "version-blockers.md"
        if not record_json.is_file() or not record_md.is_file():
            errors.append("recorded blocker ledger must write metadata JSON and Markdown")
        else:
            recorded_payload = json.loads(record_json.read_text())
            if recorded_payload.get("schemaVersion") != SCHEMA:
                errors.append("recorded blocker ledger schema mismatch")
            if "# KubeActuary Version Blockers" not in record_md.read_text():
                errors.append("recorded blocker ledger Markdown title missing")
        if markdown_result.returncode != 0 or "# KubeActuary Version Blockers" not in markdown_result.stdout:
            errors.append("ledger Markdown must render title")
        for snippet in (
            "missing-tool: `kind`",
            "environment: `cluster-unavailable`",
            "recordBlockers",
        ):
            if snippet not in markdown_result.stdout:
                errors.append(f"ledger Markdown must include: {snippet}")
        if text_result.returncode != 0 or "blocked-items: 3" not in text_result.stdout:
            errors.append("ledger text must include blocked item count")
        if invalid_version_result.returncode == 0:
            errors.append("ledger must reject unknown version filters")

    required_snippets = {
        README: ("record_version_blockers.py", "kube-actuary.version-blockers.v1"),
        README_KO: ("record_version_blockers.py", "kube-actuary.version-blockers.v1"),
        LIVE_VALIDATION: ("record_version_blockers.py", "version-blockers.json"),
        TASKBOARD: ("Version blocker ledger", "verify_version_blockers.py"),
        TEST_PLAN: ("verify_version_blockers.py", "version blocker ledger"),
        TEST_RESULTS: ("verify_version_blockers.py", "version blocker ledger"),
    }
    for path, snippets in required_snippets.items():
        text = path.read_text()
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} must document {snippet}")

    if errors:
        print("version-blockers: failed")
        for error in errors:
            print(f"error: {error}")
        return 1
    print("version-blockers: passed")
    print("blocked-items: 3")
    print("record: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
