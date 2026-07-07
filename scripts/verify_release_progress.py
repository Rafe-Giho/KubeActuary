#!/usr/bin/env python3
"""Verify versioned release progress report generation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_release_progress.py"
RECORDER = ROOT / "scripts" / "record_version_iteration.py"
README = ROOT / "README.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
sys.path.insert(0, str(ROOT))

from scripts.generate_release_progress import render_markdown, render_text  # noqa: E402
from scripts.verify_live_evidence_schema import sample  # noqa: E402


def run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GENERATOR), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_generator_with_env(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GENERATOR), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_recorder(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(RECORDER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_probe_env(path: Path) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    kubectl = path / "kubectl"
    kubectl.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"version\" ]; then\n"
        "  echo 'Client Version: fake'\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = \"cluster-info\" ]; then\n"
        "  echo 'connect: connection refused' >&2\n"
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    kubectl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(path)
    return env


def write_payload(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        evidence_dir.mkdir()
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = "kind"
        write_payload(evidence_dir / "kind.json", payload)
        write_payload(
            evidence_dir / ".kubeactuary" / "live-validation-queue.json",
            {
                "schemaVersion": "kube-actuary.live-validation-queue.v1",
                "source": "docs/release-taskboard.md",
                "mode": "inventory-plus-environment-probe",
                "clusterWrites": "disabled",
                "summary": {
                    "total": 1,
                    "toolReady": 0,
                    "blockedByTools": 0,
                    "blockedByEnvironment": 1,
                    "missingTools": [],
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
                        "environmentReason": "connection-refused",
                        "nextStep": "start or select a disposable cluster, then rerun the probe",
                        "resolvedCommands": [
                            "python3 -B scripts/capture_controller_resource_budget.py --output /tmp/kubectl-top.txt --run",
                        ],
                    }
                ],
            },
        )
        write_payload(
            evidence_dir / ".kubeactuary" / "next-version-task.json",
            {
                "schemaVersion": "kube-actuary.next-version-task.v1",
                "selected": {
                    "id": "01-controller-resource-budget",
                    "version": "Current Baseline",
                    "item": "Controller resource budget",
                    "kind": "controller-resource-budget",
                    "captureStatus": "tool-ready",
                    "resolvedCommands": [
                        "python3 -B scripts/capture_controller_resource_budget.py --output /tmp/kubectl-top.txt --run",
                        "python3 -B scripts/build_external_evidence.py --kind controller-resource-budget --source /tmp/kubectl-top.txt --output /tmp/external-evidence.json",
                    ],
                },
            },
        )
        write_payload(
            evidence_dir / ".kubeactuary" / "next-version-task-run.json",
            {
                "schemaVersion": "kube-actuary.next-version-task-run.v1",
                "mode": "run",
                "status": "failed",
                "clusterWrites": "disabled-or-server-side-dry-run-only",
                "ranAt": "2026-07-06T00:00:00+00:00",
                "nextTask": {
                    "selected": {
                        "id": "01-controller-resource-budget",
                        "version": "Current Baseline",
                        "item": "Controller resource budget",
                        "kind": "controller-resource-budget",
                        "captureStatus": "tool-ready",
                    },
                },
                "summary": {"commands": 2, "validCommands": 2, "ran": 1, "failed": 1},
                "records": [
                    {
                        "command": "python3 -B scripts/capture_controller_resource_budget.py --output /tmp/kubectl-top.txt --run",
                        "exitCode": 1,
                        "ok": False,
                        "stderr": "",
                        "stdout": "controller-resource-capture: failed\nerror: test cluster unavailable\n",
                    }
                ],
            },
        )
        write_payload(
            evidence_dir / ".kubeactuary" / "environment-probe.json",
            {
                "schemaVersion": "kube-actuary.environment-probe.v1",
                "clusterWrites": "disabled",
                "probeEnabled": False,
                "clusterAccess": "not-run",
                "summary": {"checks": 0, "passed": 0, "failed": 0},
            },
        )
        write_payload(
            evidence_dir / ".kubeactuary" / "environment-blockers.json",
            {
                "schemaVersion": "kube-actuary.environment-blockers.v1",
                "clusterWrites": "disabled",
                "summary": {
                    "clusterAccess": "not-run",
                    "blockedByEnvironment": 1,
                    "selectedBlocked": True,
                },
                "selected": {
                    "id": "01-controller-resource-budget",
                    "captureStatus": "blocked-by-environment",
                    "nextStep": "start or select a disposable cluster, then rerun the probe",
                },
            },
        )
        write_payload(
            evidence_dir / ".kubeactuary" / "version-iteration-advance.json",
            {
                "schemaVersion": "kube-actuary.version-iteration-advance.v1",
                "mode": "run",
                "status": "failed",
                "clusterWrites": "disabled-or-server-side-dry-run-only",
                "runId": "test-progress",
                "createdAt": "2026-07-06T00:00:00+00:00",
                "runner": {"status": "failed"},
                "nextTask": {
                    "selected": "01-controller-resource-budget",
                    "captureStatus": "tool-ready",
                    "skippedCompleteEvidence": 0,
                },
                "history": {"runs": 1},
                "latestBlockerStreak": {
                    "status": "repeated",
                    "streak": 2,
                    "firstRunId": "test-before",
                    "latestRunId": "test-progress",
                    "signature": {
                        "id": "01-controller-resource-budget",
                        "captureStatus": "blocked-by-environment",
                        "environmentReason": "connection-refused",
                    },
                },
            },
        )
        write_payload(
            evidence_dir / ".kubeactuary" / "next-unblock-action.json",
            {
                "schemaVersion": "kube-actuary.next-unblock-action.v1",
                "sourceWorklistQueueSource": "prepared-live-validation-queue",
                "status": "selected",
                "planStatus": "blocked",
                "clusterWrites": "disabled",
                "selectionPolicy": "highest-items-then-kind-target",
                "summary": {
                    "candidateActions": 1,
                    "blockedItems": 2,
                    "selected": True,
                },
                "selected": {
                    "id": "01-missing-tool-kind",
                    "kind": "missing-tool",
                    "tool": "kind",
                    "items": 2,
                    "affectedVersions": ["Current Baseline", "0.8.0"],
                    "nextStep": "install the missing tool or run the evidence capture on a host that already has it",
                    "commands": {"verify": ["kind version"]},
                },
            },
        )
        history_evidence_dir = tmpdir / "history-evidence"
        history_evidence_dir.mkdir()
        write_payload(
            history_evidence_dir / ".kubeactuary" / "live-validation-queue.json",
            json.loads((evidence_dir / ".kubeactuary" / "live-validation-queue.json").read_text()),
        )
        write_payload(
            history_evidence_dir / ".kubeactuary" / "version-iteration-advance.json",
            {
                "schemaVersion": "kube-actuary.version-iteration-advance.v1",
                "mode": "run",
                "status": "failed",
                "clusterWrites": "disabled-or-server-side-dry-run-only",
                "runId": "test-history-progress",
                "createdAt": "2026-07-06T00:00:00+00:00",
                "runner": {"status": "failed"},
                "nextTask": {
                    "selected": "01-controller-resource-budget",
                    "captureStatus": "blocked-by-environment",
                    "environmentStatus": "cluster-unavailable",
                    "environmentReason": "connection-refused",
                    "nextStep": "start or select a disposable cluster, then rerun the probe",
                    "skippedCompleteEvidence": 0,
                },
                "history": {"runs": 1},
            },
        )
        write_payload(
            history_evidence_dir / ".kubeactuary" / "next-unblock-action.json",
            {
                "schemaVersion": "kube-actuary.next-unblock-action.v1",
                "sourceWorklistQueueSource": "prepared-live-validation-queue",
                "status": "selected",
                "planStatus": "blocked",
                "clusterWrites": "disabled",
                "selectionPolicy": "highest-items-then-kind-target",
                "summary": {
                    "candidateActions": 1,
                    "blockedItems": 2,
                    "selected": True,
                },
                "selected": {
                    "id": "01-missing-tool-kind",
                    "kind": "missing-tool",
                    "tool": "kind",
                    "items": 2,
                    "affectedVersions": ["Current Baseline", "0.8.0"],
                    "nextStep": "install the missing tool or run the evidence capture on a host that already has it",
                    "commands": {"verify": ["kind version"]},
                },
            },
        )
        write_payload(
            history_evidence_dir / ".kubeactuary" / "next-unblock-action-run.json",
            {
                "schemaVersion": "kube-actuary.next-unblock-action-run.v1",
                "mode": "run",
                "status": "blocked",
                "clusterWrites": "disabled",
                "nextUnblockAction": {
                    "schemaVersion": "kube-actuary.next-unblock-action.v1",
                    "queueSource": "prepared-live-validation-queue",
                    "selected": {
                        "id": "01-missing-tool-kind",
                        "kind": "missing-tool",
                        "target": "kind",
                        "tool": "kind",
                        "items": 2,
                        "affectedVersions": ["Current Baseline", "0.8.0"],
                    },
                },
                "summary": {
                    "commands": 1,
                    "validCommands": 1,
                    "ran": 1,
                    "failed": 1,
                    "validationErrors": 0,
                },
                "records": [
                    {
                        "command": "kind version",
                        "stdout": "",
                        "stderr": "kind missing in progress test",
                        "exitCode": 127,
                        "ok": False,
                    }
                ],
                "failure": {
                    "command": "kind version",
                    "exitCode": 127,
                    "message": "kind missing in progress test",
                },
            },
        )
        history_dir = tmpdir / "history"
        history_recorded = run_recorder(
            str(history_dir),
            "--run-id",
            "progress-history",
            "--created-at",
            "2026-07-06T00:00:00+00:00",
            "--evidence-dir",
            str(history_evidence_dir),
        )
        probe_retry_evidence_dir = tmpdir / "probe-retry-evidence"
        (probe_retry_evidence_dir / ".kubeactuary").mkdir(parents=True)
        write_payload(
            probe_retry_evidence_dir / ".kubeactuary" / "live-validation-queue.json",
            json.loads((evidence_dir / ".kubeactuary" / "live-validation-queue.json").read_text()),
        )
        write_payload(
            probe_retry_evidence_dir / ".kubeactuary" / "version-iteration-advance.json",
            {
                "schemaVersion": "kube-actuary.version-iteration-advance.v1",
                "mode": "run",
                "status": "failed",
                "clusterWrites": "disabled-or-server-side-dry-run-only",
                "runId": "probe-retry",
                "createdAt": "2026-07-06T00:00:01+00:00",
                "runner": {"status": "failed"},
                "nextTask": {
                    "selected": "01-controller-resource-budget",
                    "captureStatus": "tool-ready",
                    "nextStep": "capture evidence with the listed commands",
                    "skippedCompleteEvidence": 0,
                },
                "history": {"runs": 1},
            },
        )
        probe_retry_history_dir = tmpdir / "probe-retry-history"
        probe_retry_recorded = run_recorder(
            str(probe_retry_history_dir),
            "--run-id",
            "probe-retry-history",
            "--created-at",
            "2026-07-06T00:00:01+00:00",
            "--evidence-dir",
            str(probe_retry_evidence_dir),
        )

        json_result = run_generator("--format", "json")
        text_result = run_generator("--format", "text")
        markdown_result = run_generator("--format", "markdown")
        version_result = run_generator("--format", "json", "--version", "0.4.3")
        version_text_result = run_generator("--format", "text", "--version", "0.4.3")
        version_markdown_result = run_generator("--format", "markdown", "--version", "0.4.3")
        probe_json_result = run_generator_with_env(
            "--format",
            "json",
            "--probe-environment",
            "--kubectl",
            "kubectl",
            env=fake_probe_env(tmpdir / "probe-tools"),
        )
        version_probe_markdown_result = run_generator_with_env(
            "--format",
            "markdown",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--kubectl",
            "kubectl",
            env=fake_probe_env(tmpdir / "version-probe-tools"),
        )
        probe_markdown_result = run_generator_with_env(
            "--format",
            "markdown",
            "--probe-environment",
            "--kubectl",
            "kubectl",
            env=fake_probe_env(tmpdir / "probe-tools-md"),
        )
        unknown_version = run_generator("--format", "json", "--version", "9.9.9")
        with_evidence = run_generator("--format", "json", "--evidence-dir", str(evidence_dir))
        with_evidence_text = run_generator("--format", "text", "--evidence-dir", str(evidence_dir))
        with_evidence_markdown = run_generator("--format", "markdown", "--evidence-dir", str(evidence_dir))
        with_history = run_generator("--format", "json", "--history-dir", str(history_dir))
        with_history_text = run_generator("--format", "text", "--history-dir", str(history_dir))
        with_history_markdown = run_generator("--format", "markdown", "--history-dir", str(history_dir))
        probe_retry_history_text = run_generator("--format", "text", "--history-dir", str(probe_retry_history_dir))
        bootstrap_history_dir = tmpdir / "bootstrap-history"
        bootstrap_history = run_generator(
            "--format",
            "json",
            "--evidence-dir",
            str(evidence_dir),
            "--history-dir",
            str(bootstrap_history_dir),
        )
        bootstrap_history_text = run_generator(
            "--format",
            "text",
            "--evidence-dir",
            str(evidence_dir),
            "--history-dir",
            str(bootstrap_history_dir),
        )
        bootstrap_history_markdown = run_generator(
            "--format",
            "markdown",
            "--evidence-dir",
            str(evidence_dir),
            "--history-dir",
            str(bootstrap_history_dir),
        )
        version_with_evidence_text = run_generator(
            "--format",
            "text",
            "--version",
            "Current Baseline",
            "--evidence-dir",
            str(evidence_dir),
        )
        missing_evidence_dir = tmpdir / "missing-evidence"
        missing_evidence = run_generator("--format", "json", "--evidence-dir", str(missing_evidence_dir))
        missing_evidence_markdown = run_generator(
            "--format",
            "markdown",
            "--evidence-dir",
            str(missing_evidence_dir),
        )
        output = tmpdir / "progress.json"
        written = run_generator("--format", "json", "--output", str(output))
        output_written = output.is_file()

    if json_result.returncode != 0:
        errors.append(f"json progress failed: {json_result.stderr.strip() or json_result.stdout.strip()}")
        progress = {}
    else:
        progress = json.loads(json_result.stdout)
        synthetic_progress = json.loads(json.dumps(progress))
        synthetic_progress["nextActions"] = {
            "source": "synthetic",
            "summary": {
                "total": 6,
                "toolReady": 6,
                "blockedByTools": 0,
                "blockedByEnvironment": 0,
            },
            "blockers": {"missingTools": [], "environment": [], "environmentNextSteps": []},
            "actions": [
                {
                    "id": f"tool-ready-{index}",
                    "item": f"Tool ready {index}",
                    "status": "tool-ready",
                    "missingTools": [],
                    "firstCommand": f"python3 -B scripts/tool_ready_{index}.py",
                }
                for index in range(1, 7)
            ],
        }
        synthetic_progress["evidenceStatus"] = {
            "summary": {
                "status": "partial",
                "coveredGates": 0,
                "totalGates": 16,
                "liveReports": 0,
                "supplementalEvidence": 0,
            },
            "nextTask": {
                "selected": {
                    "id": "synthetic-next-task",
                    "captureStatus": "blocked-by-environment",
                    "environmentStatus": "cluster-unavailable",
                    "environmentReason": "connection-refused",
                    "nextStep": "start or select a disposable cluster, then rerun the probe",
                },
            },
            "nextCommands": [
                f"python3 -B scripts/next_command_{index}.py"
                for index in range(1, 5)
            ],
        }
        synthetic_markdown = render_markdown(synthetic_progress)
        synthetic_text = render_text(synthetic_progress)
        for snippet in (
            "`tool-ready-6` Tool ready 6",
            "python3 -B scripts/tool_ready_6.py",
            "next-task-environment: `cluster-unavailable`",
            "next-task-environment-reason: `connection-refused`",
            "next-task-next-step: start or select a disposable cluster, then rerun the probe",
            "next: `python3 -B scripts/next_command_4.py`",
        ):
            if snippet not in synthetic_markdown:
                errors.append(f"markdown progress must include all runnable entries: {snippet}")
        for snippet in (
            "action: tool-ready-6 tool-ready None Tool ready 6",
            "first-command: python3 -B scripts/tool_ready_6.py",
            "next-task-environment: cluster-unavailable",
            "next-task-environment-reason: connection-refused",
            "next-task-next-step: start or select a disposable cluster, then rerun the probe",
            "next: python3 -B scripts/next_command_4.py",
        ):
            if snippet not in synthetic_text:
                errors.append(f"text progress must include all runnable entries: {snippet}")
    if text_result.returncode != 0:
        errors.append(f"text progress failed: {text_result.stderr.strip() or text_result.stdout.strip()}")
    else:
        for snippet in (
            "schema: kube-actuary.release-progress.v1",
            "verify: 16",
            "release-checks: 83",
            "version: 0.4.4 done=0 verify=1",
            "missing-tool-blocker: minikube",
            "blocker-worklist: python3 -B scripts/generate_version_worklist.py",
        ):
            if snippet not in text_result.stdout:
                errors.append(f"text progress missing detail: {snippet}")
    if markdown_result.returncode != 0 or "# KubeActuary Release Progress" not in markdown_result.stdout:
        errors.append("markdown progress output must include heading")
    if version_result.returncode != 0:
        errors.append(f"version progress failed: {version_result.stderr.strip() or version_result.stdout.strip()}")
        version_progress = {}
    else:
        version_progress = json.loads(version_result.stdout)
    if version_markdown_result.returncode != 0:
        errors.append(
            f"version progress markdown failed: {version_markdown_result.stderr.strip() or version_markdown_result.stdout.strip()}"
        )
    else:
        for snippet in (
            "versions: `0.4.3`",
            "`0.4.3` done=2 verify=1",
            "Resource budget target: idle <50m CPU and <64Mi memory",
        ):
            if snippet not in version_markdown_result.stdout:
                errors.append(f"version progress markdown missing detail: {snippet}")
        if "Current Baseline" in version_markdown_result.stdout:
            errors.append("version progress markdown must omit unrelated versions")
    if version_text_result.returncode != 0:
        errors.append(f"version progress text failed: {version_text_result.stderr.strip() or version_text_result.stdout.strip()}")
    else:
        for snippet in (
            "filter-version: 0.4.3",
            "version: 0.4.3 done=2 verify=1",
            "item: 0.4.3 VERIFY Resource budget target: idle <50m CPU and <64Mi memory",
            "action: 11-resource-budget-target-idle-50m-cpu-and-64mi-memory tool-ready 0.4.3",
        ):
            if snippet not in version_text_result.stdout:
                errors.append(f"version progress text missing detail: {snippet}")
        if "Current Baseline" in version_text_result.stdout:
            errors.append("version progress text must omit unrelated versions")
    if probe_json_result.returncode != 0:
        errors.append(f"probe progress failed: {probe_json_result.stderr.strip() or probe_json_result.stdout.strip()}")
        probe_progress = {}
    else:
        probe_progress = json.loads(probe_json_result.stdout)
    if probe_markdown_result.returncode != 0:
        errors.append(
            f"probe progress markdown failed: {probe_markdown_result.stderr.strip() or probe_markdown_result.stdout.strip()}"
        )
    else:
        for snippet in (
            "readiness-mode: `inventory-plus-environment-probe`",
            "environment-probe: `unavailable`",
            "environment-reason: `connection-refused`",
            "environment-blocked-actions: 4",
            "environment-blocker: `cluster-unavailable` (4 actions)",
            "--capture-status blocked-by-environment --environment-status cluster-unavailable",
            "--capture-status blocked-by-environment --environment-reason connection-refused",
        ):
            if snippet not in probe_markdown_result.stdout:
                errors.append(f"probe progress markdown missing detail: {snippet}")
    if version_probe_markdown_result.returncode != 0:
        errors.append(
            "version probe progress markdown failed: "
            f"{version_probe_markdown_result.stderr.strip() or version_probe_markdown_result.stdout.strip()}"
        )
    else:
        for snippet in (
            "versions: `0.4.3`",
            "environment-blocked-actions: 1",
            "environment-blocker: `cluster-unavailable` (1 actions)",
            "--version 0.4.3 --capture-status blocked-by-environment --environment-status cluster-unavailable",
        ):
            if snippet not in version_probe_markdown_result.stdout:
                errors.append(f"version probe progress markdown missing detail: {snippet}")
    if unknown_version.returncode == 0 or "unknown version: 9.9.9" not in unknown_version.stdout:
        errors.append("release progress must reject unknown version filters")
    for snippet in (
        "VERIFY: Krew manifest",
        "VERIFY: Managed Kubernetes smoke",
        "VERIFY: Controller",
        "VERIFY: Packaging",
        "VERIFY: Admission/audit",
    ):
        if snippet not in markdown_result.stdout:
            errors.append(f"markdown progress must include all open items: {snippet}")
    for snippet in (
        "missing-tool-blocker: `minikube`",
        "missing-tool-blocker: `az`",
        "missing-tool-blocker: `gcloud`",
        "worklist: `python3 -B scripts/generate_version_worklist.py --format markdown --open-only --capture-status missing-tools --missing-tool minikube`",
    ):
        if snippet not in markdown_result.stdout:
            errors.append(f"markdown progress must include all action blockers: {snippet}")
    if with_evidence.returncode != 0:
        errors.append(f"evidence progress failed: {with_evidence.stderr.strip() or with_evidence.stdout.strip()}")
        evidence_progress = {}
    else:
        evidence_progress = json.loads(with_evidence.stdout)
    if with_evidence_markdown.returncode != 0:
        errors.append(f"evidence progress markdown failed: {with_evidence_markdown.stderr.strip() or with_evidence_markdown.stdout.strip()}")
    else:
        for snippet in (
            "next-task: `01-controller-resource-budget`",
            "next-task-queue-source: `prepared-live-validation-queue`",
            "next-task-queue-source-origin: `inferred-live-validation-queue`",
            "next-task-queue-consistency: `mismatched`",
            "next-task-queue-mismatches: `captureStatus, resolvedCommands`",
            "next-task-file: `missing` `output`",
            "next-task-command: `python3 -B scripts/capture_controller_resource_budget.py",
            "next-task-run: `failed`",
            "next-task-run-queue-source: `prepared-live-validation-queue`",
            "next-task-run-queue-source-origin: `inferred-live-validation-queue`",
            "next-task-run-consistency: `matched`",
            "next-task-run-error: `error: test cluster unavailable`",
            "environment-probe: `not-run`",
            "environment-next: start or select a disposable cluster, then rerun the probe",
            "version-iteration-advance: `failed`",
            "version-iteration-advance-run-id: `test-progress`",
            "version-iteration-advance-history-runs: 1",
            "version-iteration-advance-queue-source: `prepared-live-validation-queue`",
            "version-iteration-advance-queue-source-origin: `inferred-live-validation-queue`",
            "version-iteration-advance-consistency: `matched`",
            "version-iteration-advance-blocker-streak: `2`",
            "version-iteration-advance-blocker-status: `repeated`",
            "next-action-source: `prepared-live-validation-queue`",
            "next-unblock-action: `01-missing-tool-kind` target=`kind`",
            "next-unblock-next-step: install the missing tool or run the evidence capture on a host that already has it",
            "next-unblock-retry-recommended: `true`",
            "next-unblock-retry-command: `python3 -B scripts/run_next_unblock_action.py",
            "environment-blocked-actions: 1",
            "environment-blocker: `cluster-unavailable` (1 actions)",
            "environment-reason-blocker: `connection-refused` (1 actions)",
            "generate_version_worklist.py --format markdown --open-only --evidence-dir",
            "--capture-status blocked-by-environment --environment-status cluster-unavailable",
            "--capture-status blocked-by-environment --environment-reason connection-refused",
            "blocker-next-step: start or select a disposable cluster, then rerun the probe (1 actions)",
            "prepare_live_evidence_directory.py",
        ):
            if snippet not in with_evidence_markdown.stdout:
                errors.append(f"evidence progress markdown missing status detail: {snippet}")
    if with_evidence_text.returncode != 0:
        errors.append(f"evidence progress text failed: {with_evidence_text.stderr.strip() or with_evidence_text.stdout.strip()}")
    else:
        for snippet in (
            "evidence-status: partial",
            "next-action-source: prepared-live-validation-queue",
            "environment-blocker: cluster-unavailable actions=1",
            "next-task: 01-controller-resource-budget tool-ready",
            "next-task-run: failed run",
            "version-iteration-advance: failed",
            "version-iteration-advance-blocker-streak: 2",
            "version-iteration-advance-blocker-status: repeated",
            "next-unblock-action: 01-missing-tool-kind kind",
            "next-unblock-next-step: install the missing tool or run the evidence capture on a host that already has it",
            "next-unblock-retry-recommended: true",
            "next-unblock-retry-command: python3 -B scripts/run_next_unblock_action.py",
            "evidence-environment-probe-retry-command: python3 -B scripts/prepare_live_evidence_directory.py",
        ):
            if snippet not in with_evidence_text.stdout:
                errors.append(f"evidence progress text missing status detail: {snippet}")
    if history_recorded.returncode != 0:
        errors.append(f"history fixture failed: {history_recorded.stderr.strip() or history_recorded.stdout.strip()}")
        history_progress = {}
    elif with_history.returncode != 0:
        errors.append(f"history progress failed: {with_history.stderr.strip() or with_history.stdout.strip()}")
        history_progress = {}
    else:
        history_progress = json.loads(with_history.stdout)
    history_status = history_progress.get("versionHistoryStatus", {})
    if history_status:
        if history_status.get("schemaVersion") != "kube-actuary.version-iteration-history-status.v1":
            errors.append("history progress must include version history status schema")
        if history_status.get("valid") is not True:
            errors.append("history progress must report a valid history fixture")
        if history_status.get("summary", {}).get("latestRunId") != "progress-history":
            errors.append("history progress must preserve latest history run id")
        if history_status.get("latestAdvance", {}).get("status") != "failed":
            errors.append("history progress must include latest advance status")
        if history_status.get("latestAdvance", {}).get("nextTaskConsistency", {}).get("status") != "matched":
            errors.append("history progress must include latest advance consistency")
        latest_unblock = history_status.get("latestNextUnblockAction", {})
        if latest_unblock.get("selected", {}).get("id") != "01-missing-tool-kind":
            errors.append("history progress must include latest next-unblock action")
        latest_unblock_run = history_status.get("latestNextUnblockActionRun", {})
        if latest_unblock_run.get("status") != "blocked":
            errors.append("history progress must include latest next-unblock runner status")
        if (latest_unblock_run.get("failure") or {}).get("message") != "kind missing in progress test":
            errors.append("history progress must include latest next-unblock runner failure")
        latest_unblock_retry = history_status.get("latestNextUnblockRetry", {})
        if latest_unblock_retry.get("recommended") is not False:
            errors.append("history progress must suppress next-unblock retry before tool resolution")
        if latest_unblock_retry.get("retryAfter") != "required local tools are installed":
            errors.append("history progress must explain when next-unblock retry is useful")
        blocker_streak = history_status.get("latestBlockerStreak", {})
        if blocker_streak.get("streak") != 1 or blocker_streak.get("status") != "single":
            errors.append("history progress must include latest blocker streak")
        blocker_action = history_status.get("latestBlockerAction", {})
        if blocker_action.get("action") != "resolve-environment":
            errors.append("history progress must include latest blocker action")
        if blocker_action.get("retryRecommended") is not False:
            errors.append("history progress must suppress retry before blocker resolution")
    elif history_recorded.returncode == 0 and with_history.returncode == 0:
        errors.append("history progress must include versionHistoryStatus")
    if with_history_text.returncode != 0:
        errors.append(f"history progress text failed: {with_history_text.stderr.strip() or with_history_text.stdout.strip()}")
    else:
        for snippet in (
            "history-status: valid",
            "history-runs: 1",
            "history-latest-run-id: progress-history",
            "history-latest-advance-status: failed",
            "history-latest-advance-next-task-consistency: matched",
            "history-latest-next-unblock: 01-missing-tool-kind kind",
            "history-latest-next-unblock-run: blocked run",
            "history-latest-next-unblock-run-error: kind missing in progress test",
            "history-latest-next-unblock-retry-recommended: false",
            "history-latest-next-unblock-retry-after: required local tools are installed",
            "history-latest-next-unblock-retry-command: python3 -B scripts/run_next_unblock_action.py",
            "history-latest-blocker-streak: 1",
            "history-latest-blocker-status: single",
            "history-latest-blocker-action: resolve-environment",
            "history-latest-blocker-retry-recommended: false",
            "history-latest-blocker-retry-after: environment probe succeeds",
            "history-latest-blocker-retry-command: python3 -B scripts/advance_version_iteration.py",
            "history-next: python3 -B scripts/inspect_version_history.py",
        ):
            if snippet not in with_history_text.stdout:
                errors.append(f"history progress text missing status detail: {snippet}")
    expected_probe_retry_command = (
        f"history-next: python3 -B scripts/advance_version_iteration.py "
        f"{probe_retry_evidence_dir} {probe_retry_history_dir} --probe-environment --run"
    )
    if probe_retry_recorded.returncode != 0:
        errors.append(
            "probe retry history fixture failed: "
            f"{probe_retry_recorded.stderr.strip() or probe_retry_recorded.stdout.strip()}"
        )
    elif probe_retry_history_text.returncode != 0:
        errors.append(
            "probe retry history progress text failed: "
            f"{probe_retry_history_text.stderr.strip() or probe_retry_history_text.stdout.strip()}"
        )
    elif expected_probe_retry_command not in probe_retry_history_text.stdout:
        errors.append("probe retry history progress text should add --probe-environment after failed tool-ready advance")
    if with_history_markdown.returncode != 0:
        errors.append(
            f"history progress markdown failed: {with_history_markdown.stderr.strip() or with_history_markdown.stdout.strip()}"
        )
    else:
        for snippet in (
            "## Version History",
            "status: valid",
            "latest run: `progress-history`",
            "latest advance: `failed`",
            "latest advance next task consistency: `matched`",
            "latest next unblock: `01-missing-tool-kind` target=`kind`",
            "latest next unblock run: `blocked` (run)",
            "latest next unblock run error: `kind missing in progress test`",
            "latest next unblock retry recommended: `false`",
            "latest next unblock retry after: required local tools are installed",
            "latest next unblock retry command: `python3 -B scripts/run_next_unblock_action.py",
            "latest blocker streak: `1` (single)",
            "latest blocker action: `resolve-environment`",
            "latest blocker retry recommended: `false`",
            "latest blocker retry after: environment probe succeeds",
            "latest blocker retry command: `python3 -B scripts/advance_version_iteration.py",
            "history next: `python3 -B scripts/inspect_version_history.py",
        ):
            if snippet not in with_history_markdown.stdout:
                errors.append(f"history progress markdown missing status detail: {snippet}")
    expected_bootstrap_command = (
        f"python3 -B scripts/record_version_iteration.py {bootstrap_history_dir} "
        f"--evidence-dir {evidence_dir}"
    )
    if bootstrap_history.returncode != 0:
        errors.append(
            "bootstrap history progress failed: "
            f"{bootstrap_history.stderr.strip() or bootstrap_history.stdout.strip()}"
        )
    else:
        bootstrap_payload = json.loads(bootstrap_history.stdout)
        bootstrap_history_status = bootstrap_payload.get("versionHistoryStatus", {})
        if expected_bootstrap_command not in bootstrap_history_status.get("nextCommands", []):
            errors.append("bootstrap history progress should recommend the initial evidence-aware history record")
    if bootstrap_history_text.returncode != 0:
        errors.append(
            "bootstrap history progress text failed: "
            f"{bootstrap_history_text.stderr.strip() or bootstrap_history_text.stdout.strip()}"
        )
    elif f"history-next: {expected_bootstrap_command}" not in bootstrap_history_text.stdout:
        errors.append("bootstrap history progress text should show the initial record command")
    if bootstrap_history_markdown.returncode != 0:
        errors.append(
            "bootstrap history progress markdown failed: "
            f"{bootstrap_history_markdown.stderr.strip() or bootstrap_history_markdown.stdout.strip()}"
        )
    elif f"history next: `{expected_bootstrap_command}`" not in bootstrap_history_markdown.stdout:
        errors.append("bootstrap history progress markdown should show the initial record command")
    if version_with_evidence_text.returncode != 0:
        errors.append(
            "version evidence progress text failed: "
            f"{version_with_evidence_text.stderr.strip() or version_with_evidence_text.stdout.strip()}"
        )
    else:
        for snippet in (
            "filter-version: Current Baseline",
            "evidence-covered: 0/8",
            "--version 'Current Baseline' --capture-status blocked-by-environment --environment-status cluster-unavailable",
            "--version 'Current Baseline' --capture-status blocked-by-environment --environment-reason connection-refused",
            f"evidence-environment-probe-retry-command: python3 -B scripts/prepare_live_evidence_directory.py {evidence_dir} --version 'Current Baseline' --probe-environment",
        ):
            if snippet not in version_with_evidence_text.stdout:
                errors.append(f"version evidence progress text missing status detail: {snippet}")
    if missing_evidence.returncode != 0:
        errors.append(f"missing evidence progress failed: {missing_evidence.stderr.strip() or missing_evidence.stdout.strip()}")
        missing_evidence_progress = {}
    else:
        missing_evidence_progress = json.loads(missing_evidence.stdout)
    if missing_evidence_markdown.returncode != 0 or "status: not-prepared" not in missing_evidence_markdown.stdout:
        errors.append("missing evidence markdown must report not-prepared status")
    if written.returncode != 0 or not output_written:
        errors.append("progress generator must write requested output file")

    if progress.get("schemaVersion") != "kube-actuary.release-progress.v1":
        errors.append("release progress schemaVersion mismatch")
    if progress.get("releaseSuite", {}).get("checks") != 83:
        errors.append("release progress must report 83 release checks")
    if progress.get("summary", {}).get("verify") != 16:
        errors.append("release progress must report 16 VERIFY rows")
    if progress.get("summary", {}).get("doing") != 0 or progress.get("summary", {}).get("todo") != 0:
        errors.append("release progress must report zero DOING/TODO rows")
    versions = {group.get("version"): group for group in progress.get("versions", [])}
    for expected in ("Current Baseline", "0.2.0", "0.4.4", "0.9.0"):
        if expected not in versions:
            errors.append(f"release progress missing version group: {expected}")
    if versions.get("0.2.0", {}).get("summary", {}).get("done") != 3:
        errors.append("v0.2.0 group should remain fully DONE")
    if versions.get("0.4.4", {}).get("summary", {}).get("verify") != 1:
        errors.append("v0.4.4 group should keep lightweight smoke VERIFY")
    if progress.get("externalGatePlan", {}).get("verify") != 16:
        errors.append("progress report must include external gate summary")
    if version_progress.get("filters", {}).get("versions") != ["0.4.3"]:
        errors.append("version progress must preserve version filters")
    if version_progress.get("summary", {}).get("rows") != 3 or version_progress.get("summary", {}).get("verify") != 1:
        errors.append("version progress must narrow summary rows to the requested version")
    version_groups = version_progress.get("versions", [])
    if len(version_groups) != 1 or version_groups[0].get("version") != "0.4.3":
        errors.append("version progress must include only the requested version group")
    if version_progress.get("externalGatePlan", {}).get("verify") != 1:
        errors.append("version progress must narrow external gate plan")
    version_actions = version_progress.get("nextActions", {}).get("actions", [])
    if len(version_actions) != 1 or version_actions[0].get("id") != "11-resource-budget-target-idle-50m-cpu-and-64mi-memory":
        errors.append("version progress must narrow next actions to the requested version")
    readiness = progress.get("liveValidationReadiness", {}).get("summary", {})
    if readiness.get("liveGates") != 7 or "toolReadyGates" not in readiness:
        errors.append("progress report must include live readiness summary")
    next_actions = progress.get("nextActions", {})
    if next_actions.get("summary", {}).get("total") != 16:
        errors.append("progress report must include one next action per external gate")
    blockers = next_actions.get("blockers", {})
    if next_actions.get("summary", {}).get("blockedByTools", 0) and not blockers.get("missingTools"):
        errors.append("progress report must summarize missing tool blockers")
    minikube_blocker = next(
        (item for item in blockers.get("missingTools", []) if item.get("tool") == "minikube"),
        {},
    )
    if "--missing-tool minikube" not in minikube_blocker.get("worklistCommand", ""):
        errors.append("progress missing-tool blockers must include filtered worklist commands")
    for action in next_actions.get("actions", []):
        if action.get("status") not in {"tool-ready", "missing-tools"}:
            errors.append(f"invalid next action status: {action.get('status')!r}")
        if "missingTools" not in action:
            errors.append("next action must include missingTools")
        if action.get("status") != "tool-ready" and action.get("firstCommand"):
            errors.append("blocked inventory next actions must not expose runnable firstCommand")
    if not any(action.get("firstCommand") for action in next_actions.get("actions", [])):
        errors.append("next actions must include recommended commands")
    probe_readiness = probe_progress.get("liveValidationReadiness", {})
    probe_summary = probe_progress.get("nextActions", {}).get("summary", {})
    probe_blockers = probe_progress.get("nextActions", {}).get("blockers", {})
    if probe_readiness.get("mode") != "inventory-plus-environment-probe":
        errors.append("probe progress must run readiness in environment-probe mode")
    probe = probe_readiness.get("environmentProbe") or {}
    if probe.get("clusterAccess") != "unavailable" or probe.get("reason") != "connection-refused":
        errors.append("probe progress must preserve environment probe result and reason")
    if probe_summary.get("toolReady") != 0 or probe_summary.get("blockedByEnvironment") != 4:
        errors.append("probe progress must move kubectl-only actions to environment blockers")
    probe_actions = probe_progress.get("nextActions", {}).get("actions", [])
    if any(action.get("status") == "blocked-by-environment" and action.get("firstCommand") for action in probe_actions):
        errors.append("probe progress must not expose runnable commands for environment-blocked actions")
    if not all(
        action.get("environmentReason") == "connection-refused"
        for action in probe_actions
        if action.get("status") == "blocked-by-environment"
    ):
        errors.append("probe progress must preserve environment reason on blocked actions")
    if probe_blockers.get("environment") != [{"status": "cluster-unavailable", "actions": 4, "worklistCommand": "python3 -B scripts/generate_version_worklist.py --format markdown --open-only --capture-status blocked-by-environment --environment-status cluster-unavailable"}]:
        errors.append("probe progress must summarize environment blocker drilldowns")
    evidence_status = evidence_progress.get("evidenceStatus", {})
    if evidence_status.get("summary", {}).get("status") != "partial":
        errors.append("progress report must include partial evidence-dir status")
    if not evidence_status.get("nextCommands"):
        errors.append("partial evidence progress must include next commands")
    if any("capture_controller_resource_budget.py" in command for command in evidence_status.get("nextCommands", [])):
        errors.append("environment-blocked evidence progress must not recommend capture commands")
    if (evidence_status.get("nextTask") or {}).get("queueSource") != "prepared-live-validation-queue":
        errors.append("evidence progress must preserve next-task queue source")
    if (evidence_status.get("nextTask") or {}).get("queueSourceOrigin") != "inferred-live-validation-queue":
        errors.append("evidence progress must preserve next-task queue source origin")
    next_task_consistency = (evidence_status.get("nextTask") or {}).get("queueConsistency") or {}
    if next_task_consistency.get("status") != "mismatched":
        errors.append("evidence progress must preserve next-task queue consistency")
    if next_task_consistency.get("mismatches") != ["captureStatus", "resolvedCommands"]:
        errors.append("evidence progress must preserve next-task queue mismatch fields")
    if (evidence_status.get("nextTaskRun") or {}).get("queueSource") != "prepared-live-validation-queue":
        errors.append("evidence progress must preserve next-task-run queue source")
    if (evidence_status.get("nextTaskRun") or {}).get("queueSourceOrigin") != "inferred-live-validation-queue":
        errors.append("evidence progress must preserve next-task-run queue source origin")
    if (evidence_status.get("nextTaskRun") or {}).get("nextTaskConsistency", {}).get("status") != "matched":
        errors.append("evidence progress must preserve next-task-run consistency")
    if (evidence_status.get("versionIterationAdvance") or {}).get("queueSource") != "prepared-live-validation-queue":
        errors.append("evidence progress must preserve advance queue source")
    if (evidence_status.get("versionIterationAdvance") or {}).get("queueSourceOrigin") != "inferred-live-validation-queue":
        errors.append("evidence progress must preserve advance queue source origin")
    if (evidence_status.get("versionIterationAdvance") or {}).get("nextTaskConsistency", {}).get("status") != "matched":
        errors.append("evidence progress must preserve advance next-task consistency")
    evidence_queue = evidence_progress.get("liveValidationQueue", {})
    evidence_next_actions = evidence_progress.get("nextActions", {})
    if evidence_queue.get("schemaVersion") != "kube-actuary.live-validation-queue.v1":
        errors.append("evidence progress must include the persisted live validation queue summary")
    if evidence_next_actions.get("source") != "prepared-live-validation-queue":
        errors.append("evidence progress must use the persisted live validation queue as next action source")
    if evidence_next_actions.get("summary", {}).get("blockedByEnvironment") != 1:
        errors.append("evidence progress must preserve persisted environment-blocked action count")
    if (evidence_next_actions.get("actions") or [{}])[0].get("environmentStatus") != "cluster-unavailable":
        errors.append("evidence progress next actions must preserve environment status")
    if any(
        action.get("status") != "tool-ready" and action.get("firstCommand")
        for action in evidence_next_actions.get("actions", [])
    ):
        errors.append("blocked evidence next actions must not expose runnable firstCommand")
    evidence_blockers = evidence_next_actions.get("blockers", {})
    environment_summary = [
        {"status": item.get("status"), "actions": item.get("actions")}
        for item in evidence_blockers.get("environment", [])
    ]
    if environment_summary != [{"status": "cluster-unavailable", "actions": 1}]:
        errors.append("evidence progress must summarize environment blockers")
    environment_reason_summary = [
        {"reason": item.get("reason"), "actions": item.get("actions")}
        for item in evidence_blockers.get("environmentReasons", [])
    ]
    if environment_reason_summary != [{"reason": "connection-refused", "actions": 1}]:
        errors.append("evidence progress must summarize environment reason blockers")
    environment_commands = [
        item.get("worklistCommand", "")
        for item in evidence_blockers.get("environment", [])
        if item.get("status") == "cluster-unavailable"
    ]
    if not environment_commands or "--evidence-dir" not in environment_commands[0]:
        errors.append("evidence environment blockers must include evidence-aware worklist commands")
    if evidence_blockers.get("environmentNextSteps") != [
        {"nextStep": "start or select a disposable cluster, then rerun the probe", "actions": 1}
    ]:
        errors.append("evidence progress must summarize environment blocker next steps")
    missing_status = missing_evidence_progress.get("evidenceStatus", {})
    if missing_status.get("summary", {}).get("status") != "not-prepared":
        errors.append("missing evidence progress must report not-prepared status")
    if missing_status.get("summary", {}).get("totalGates") != 16:
        errors.append("missing evidence progress must preserve external gate count")
    if not any("prepare_live_evidence_directory.py" in command for command in missing_status.get("nextCommands", [])):
        errors.append("missing evidence progress must recommend preparing the evidence directory")

    for snippet in ("generate_release_progress.py", "kube-actuary.release-progress.v1"):
        if snippet not in README.read_text():
            errors.append(f"README missing release progress detail: {snippet}")
    for snippet in ("Release progress", "verify_release_progress.py"):
        if snippet not in TASKBOARD.read_text():
            errors.append(f"taskboard missing release progress detail: {snippet}")

    if errors:
        print("release-progress: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("release-progress: passed")
    print("versions: ok")
    print("verify: 16")
    print("checks: 83")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
