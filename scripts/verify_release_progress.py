#!/usr/bin/env python3
"""Verify versioned release progress report generation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_release_progress.py"
README = ROOT / "README.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
sys.path.insert(0, str(ROOT))

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
                    "skippedCompleteEvidence": 0,
                },
                "history": {"runs": 1},
            },
        )

        json_result = run_generator("--format", "json")
        markdown_result = run_generator("--format", "markdown")
        with_evidence = run_generator("--format", "json", "--evidence-dir", str(evidence_dir))
        with_evidence_markdown = run_generator("--format", "markdown", "--evidence-dir", str(evidence_dir))
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
    if markdown_result.returncode != 0 or "# KubeActuary Release Progress" not in markdown_result.stdout:
        errors.append("markdown progress output must include heading")
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
            "next-task-run: `failed`",
            "next-task-run-queue-source: `prepared-live-validation-queue`",
            "next-task-run-queue-source-origin: `inferred-live-validation-queue`",
            "next-task-run-error: `error: test cluster unavailable`",
            "environment-probe: `not-run`",
            "environment-next: start or select a disposable cluster, then rerun the probe",
            "version-iteration-advance: `failed`",
            "version-iteration-advance-queue-source: `prepared-live-validation-queue`",
            "version-iteration-advance-queue-source-origin: `inferred-live-validation-queue`",
            "next-action-source: `prepared-live-validation-queue`",
            "environment-blocked-actions: 1",
            "prepare_live_evidence_directory.py",
        ):
            if snippet not in with_evidence_markdown.stdout:
                errors.append(f"evidence progress markdown missing status detail: {snippet}")
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
    if progress.get("releaseSuite", {}).get("checks") != 79:
        errors.append("release progress must report 79 release checks")
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
    readiness = progress.get("liveValidationReadiness", {}).get("summary", {})
    if readiness.get("liveGates") != 7 or "toolReadyGates" not in readiness:
        errors.append("progress report must include live readiness summary")
    next_actions = progress.get("nextActions", {})
    if next_actions.get("summary", {}).get("total") != 16:
        errors.append("progress report must include one next action per external gate")
    for action in next_actions.get("actions", []):
        if action.get("status") not in {"tool-ready", "missing-tools"}:
            errors.append(f"invalid next action status: {action.get('status')!r}")
        if "missingTools" not in action:
            errors.append("next action must include missingTools")
    if not any(action.get("firstCommand") for action in next_actions.get("actions", [])):
        errors.append("next actions must include recommended commands")
    evidence_status = evidence_progress.get("evidenceStatus", {})
    if evidence_status.get("summary", {}).get("status") != "partial":
        errors.append("progress report must include partial evidence-dir status")
    if not evidence_status.get("nextCommands"):
        errors.append("partial evidence progress must include next commands")
    if (evidence_status.get("nextTask") or {}).get("queueSource") != "prepared-live-validation-queue":
        errors.append("evidence progress must preserve next-task queue source")
    if (evidence_status.get("nextTask") or {}).get("queueSourceOrigin") != "inferred-live-validation-queue":
        errors.append("evidence progress must preserve next-task queue source origin")
    if (evidence_status.get("nextTaskRun") or {}).get("queueSource") != "prepared-live-validation-queue":
        errors.append("evidence progress must preserve next-task-run queue source")
    if (evidence_status.get("nextTaskRun") or {}).get("queueSourceOrigin") != "inferred-live-validation-queue":
        errors.append("evidence progress must preserve next-task-run queue source origin")
    if (evidence_status.get("versionIterationAdvance") or {}).get("queueSource") != "prepared-live-validation-queue":
        errors.append("evidence progress must preserve advance queue source")
    if (evidence_status.get("versionIterationAdvance") or {}).get("queueSourceOrigin") != "inferred-live-validation-queue":
        errors.append("evidence progress must preserve advance queue source origin")
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
    print("checks: 79")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
