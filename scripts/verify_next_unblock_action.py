#!/usr/bin/env python3
"""Verify next unblock action selection and recording."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "scripts" / "select_next_unblock_action.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
TEST_PLAN = ROOT / "docs" / "test-plan-v0.2.0.md"
TEST_RESULTS = ROOT / "docs" / "test-results-v0.2.0.md"
SCHEMA = "kube-actuary.next-unblock-action.v1"


def run_selector(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SELECTOR), *args],
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
                    "total": 4,
                    "toolReady": 0,
                    "blockedByTools": 3,
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
                    {
                        "id": "15-validating-admission-webhook-prototype",
                        "version": "0.8.0",
                        "item": "Validating admission webhook prototype",
                        "kind": "admission",
                        "status": "missing-tools",
                        "missingTools": ["kind"],
                        "nextStep": "install missing tools or run on a host that has them",
                        "commands": [
                            "python3 -B scripts/run_admission_kind_smoke.py --run --output <path>",
                        ],
                        "resolvedCommands": [
                            (
                                "python3 -B scripts/run_admission_kind_smoke.py --run "
                                f"--output {evidence_dir.as_posix()}/reports/15-validating-admission-webhook-prototype-admission-kind-smoke.json"
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
        json_result = run_selector("--format", "json", "--evidence-dir", str(evidence_dir))
        markdown_result = run_selector("--format", "markdown", "--evidence-dir", str(evidence_dir))
        text_result = run_selector("--format", "text", "--evidence-dir", str(evidence_dir))
        helm_result = run_selector(
            "--format",
            "json",
            "--evidence-dir",
            str(evidence_dir),
            "--missing-tool",
            "helm",
        )
        environment_result = run_selector(
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
        output_path = tmpdir / "next-unblock.txt"
        recorded_result = run_selector(
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
        invalid_version_result = run_selector("--version", "9.9.9")

        payload = parse_json("next unblock action", json_result, errors)
        helm_payload = parse_json("helm next unblock action", helm_result, errors)
        environment_payload = parse_json("environment next unblock action", environment_result, errors)
        selected = payload.get("selected") or {}
        summary = payload.get("summary") or {}
        if payload.get("schemaVersion") != SCHEMA:
            errors.append("next unblock action schemaVersion mismatch")
        if payload.get("sourcePlanSchema") != "kube-actuary.version-unblock-plan.v1":
            errors.append("next unblock action must derive from unblock plan")
        if payload.get("sourceBlockerSchema") != "kube-actuary.version-blockers.v1":
            errors.append("next unblock action must preserve blocker schema")
        if payload.get("sourceWorklistQueueSource") != "prepared-live-validation-queue":
            errors.append("next unblock action must use prepared queue source")
        if payload.get("clusterWrites") != "disabled":
            errors.append("next unblock action must keep writes disabled")
        if payload.get("selectionPolicy") != "highest-items-then-kind-target":
            errors.append("next unblock action selection policy mismatch")
        if summary.get("candidateActions") != 3 or summary.get("selected") is not True:
            errors.append("next unblock action must summarize fixture actions")
        if selected.get("kind") != "missing-tool" or selected.get("tool") != "kind":
            errors.append("next unblock action must pick highest-impact kind blocker")
        if selected.get("items") != 2:
            errors.append("next unblock action must preserve selected item count")
        if "kind version" not in (selected.get("commands") or {}).get("verify", []):
            errors.append("next unblock action must include selected verify command")
        helm_selected = helm_payload.get("selected") or {}
        if helm_selected.get("tool") != "helm" or helm_payload.get("summary", {}).get("candidateActions") != 1:
            errors.append("missing-tool filter must select helm action only")
        env_selected = environment_payload.get("selected") or {}
        if env_selected.get("kind") != "environment" or env_selected.get("environmentReason") != "command-failed":
            errors.append("environment filter must select environment unblock action")
        if "kubectl cluster-info --request-timeout=5s" not in (env_selected.get("commands") or {}).get("verify", []):
            errors.append("environment action must include cluster-info verifier")
        if recorded_result.returncode != 0:
            errors.append(f"recorded next unblock action failed: {recorded_result.stderr.strip() or recorded_result.stdout.strip()}")
        if not output_path.is_file():
            errors.append("recorded next unblock action must write requested output")
        record_json = record_dir / "next-unblock-action.json"
        record_md = record_dir / "next-unblock-action.md"
        if not record_json.is_file() or not record_md.is_file():
            errors.append("recorded next unblock action must write JSON and Markdown")
        else:
            recorded_payload = json.loads(record_json.read_text())
            if recorded_payload.get("schemaVersion") != SCHEMA:
                errors.append("recorded next unblock action schema mismatch")
            if "# KubeActuary Next Unblock Action" not in record_md.read_text():
                errors.append("recorded next unblock action Markdown title missing")
        if markdown_result.returncode != 0:
            errors.append(f"next unblock action Markdown failed: {markdown_result.stderr.strip() or markdown_result.stdout.strip()}")
        for snippet in (
            "# KubeActuary Next Unblock Action",
            "Selection policy: `highest-items-then-kind-target`",
            "missing-tool `kind`",
            "kind version",
        ):
            if snippet not in markdown_result.stdout:
                errors.append(f"next unblock action Markdown must include: {snippet}")
        if text_result.returncode != 0:
            errors.append(f"next unblock action text failed: {text_result.stderr.strip() or text_result.stdout.strip()}")
        for snippet in ("next-unblock-action: selected", "target: kind", "action-items: 2"):
            if snippet not in text_result.stdout:
                errors.append(f"next unblock action text must include: {snippet}")
        if invalid_version_result.returncode == 0:
            errors.append("next unblock action must reject unknown version filters")

    required_snippets = {
        README: ("select_next_unblock_action.py", "kube-actuary.next-unblock-action.v1"),
        README_KO: ("select_next_unblock_action.py", "kube-actuary.next-unblock-action.v1"),
        LIVE_VALIDATION: ("select_next_unblock_action.py", "next-unblock-action.json"),
        TASKBOARD: ("Next unblock action", "verify_next_unblock_action.py"),
        TEST_PLAN: ("verify_next_unblock_action.py", "next unblock action"),
        TEST_RESULTS: ("verify_next_unblock_action.py", "next unblock action"),
    }
    for path, snippets in required_snippets.items():
        text = path.read_text()
        for snippet in snippets:
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} must document {snippet}")

    if errors:
        print("next-unblock-action: failed")
        for error in errors:
            print(f"error: {error}")
        return 1
    print("next-unblock-action: passed")
    print("target: kind")
    print("record: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
