#!/usr/bin/env python3
"""Verify version worklist generation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "generate_version_worklist.py"
PREPARE = ROOT / "scripts" / "prepare_version_iteration.py"
PREPARE_LIVE = ROOT / "scripts" / "prepare_live_evidence_directory.py"
COMPARE = ROOT / "scripts" / "compare_version_iterations.py"
RECORD = ROOT / "scripts" / "record_version_iteration.py"
INSPECT_HISTORY = ROOT / "scripts" / "inspect_version_history.py"
SELECT = ROOT / "scripts" / "select_next_version_task.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
WORKLIST_TOOL = "generate_version_worklist.py"
PREPARE_TOOL = "prepare_version_iteration.py"
PREPARE_LIVE_TOOL = "prepare_live_evidence_directory.py"
COMPARE_TOOL = "compare_version_iterations.py"
RECORD_TOOL = "record_version_iteration.py"
INSPECT_HISTORY_TOOL = "inspect_version_history.py"
SELECT_TOOL = "select_next_version_task.py"
VERIFY_TOOL = "verify_version_worklist.py"
SCHEMA = "kube-actuary.version-worklist.v1"
ITERATION_SCHEMA = "kube-actuary.version-iteration.v1"
DIFF_SCHEMA = "kube-actuary.version-iteration-diff.v1"
HISTORY_SCHEMA = "kube-actuary.version-iteration-history.v1"
HISTORY_STATUS_SCHEMA = "kube-actuary.version-iteration-history-status.v1"
NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"


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


def run_prepare(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(PREPARE), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_prepare_live(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(PREPARE_LIVE), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_compare(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(COMPARE), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_record(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(RECORD), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_inspect_history(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(INSPECT_HISTORY), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_select(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(SELECT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def parse_worklist(label: str, result: subprocess.CompletedProcess[str], errors: list[str]) -> dict:
    if result.returncode != 0:
        errors.append(f"{label} failed: {result.stderr.strip() or result.stdout.strip()}")
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"{label} must parse: {exc}")
        return {}


def fake_all_tools_env(path: Path, cluster_ok: bool) -> dict[str, str]:
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
        "        print('cluster unavailable from fake kubectl', file=sys.stderr)\n"
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
    text_result = run_generator("--format", "text", "--open-only")
    single_version_result = run_generator("--format", "json", "--version", "0.4.3")
    multi_version_result = run_generator("--format", "json", "--version", "0.3.3", "--version", "0.4.3")
    open_only_result = run_generator("--format", "json", "--open-only")
    filtered_missing_status_result = run_generator("--format", "json", "--open-only", "--capture-status", "missing-tools")
    filtered_kind_result = run_generator("--format", "json", "--open-only", "--missing-tool", "kind")
    filtered_kind_markdown = run_generator("--format", "markdown", "--open-only", "--missing-tool", "kind")
    invalid_version_result = run_generator("--version", "9.9.9")
    next_task_result = run_select("--format", "json")
    next_task_markdown = run_select("--format", "markdown")
    next_task_version = run_select("--format", "json", "--version", "0.4.3")
    next_task_missing = run_select("--format", "json", "--version", "0.4.4")
    next_task_kind = run_select("--format", "json", "--missing-tool", "kind")
    next_task_paths = run_select("--format", "json", "--evidence-dir", "evidence/live")
    next_task_runnable_only = run_select("--format", "json", "--runnable-only")
    next_task_blocked_only = run_select("--format", "json", "--blocked-only")
    next_task_blocked_only_text = run_select("--format", "text", "--blocked-only")
    next_task_filter_conflict = run_select("--runnable-only", "--blocked-only")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        output = tmpdir / "worklist.json"
        written = run_generator("--output", str(output))
        output_written = output.is_file()
        probe_env = fake_all_tools_env(tmpdir / "tools", cluster_ok=False)
        probe_result = run_generator("--format", "json", "--open-only", "--probe-environment", env=probe_env)
        probe_next_task = run_select("--format", "json", "--probe-environment", env=probe_env)
        prepared_queue_dir = tmpdir / "prepared-queue"
        prepared_queue = run_prepare_live(str(prepared_queue_dir), "--probe-environment", env=probe_env)
        prepared_queue_worklist_result = run_generator(
            "--format",
            "json",
            "--open-only",
            "--evidence-dir",
            str(prepared_queue_dir),
        )
        prepared_queue_worklist_markdown = run_generator(
            "--format",
            "markdown",
            "--open-only",
            "--evidence-dir",
            str(prepared_queue_dir),
        )
        prepared_environment_filter_result = run_generator(
            "--format",
            "json",
            "--open-only",
            "--evidence-dir",
            str(prepared_queue_dir),
            "--environment-status",
            "cluster-unavailable",
        )
        prepared_environment_reason_filter_result = run_generator(
            "--format",
            "json",
            "--open-only",
            "--evidence-dir",
            str(prepared_queue_dir),
            "--environment-reason",
            "command-failed",
        )
        prepared_capture_filter_result = run_generator(
            "--format",
            "json",
            "--open-only",
            "--evidence-dir",
            str(prepared_queue_dir),
            "--capture-status",
            "tool-ready",
        )
        prepared_queue_next_task = run_select(
            "--format",
            "json",
            "--evidence-dir",
            str(prepared_queue_dir),
        )
        prepared_queue_next_markdown = run_select(
            "--format",
            "markdown",
            "--evidence-dir",
            str(prepared_queue_dir),
        )
        prepared_queue_iteration_dir = tmpdir / "prepared-queue-iteration"
        prepared_queue_iteration = run_prepare(
            str(prepared_queue_iteration_dir),
            "--open-only",
            "--evidence-dir",
            str(prepared_queue_dir),
        )
        prepared_queue_iteration_readme = (
            prepared_queue_iteration_dir / "README.md"
        ).read_text() if (prepared_queue_iteration_dir / "README.md").is_file() else ""
        prepared_queue_iteration_path = prepared_queue_iteration_dir / "versions" / "current-baseline.json"
        prepared_queue_iteration_payload = (
            json.loads(prepared_queue_iteration_path.read_text()) if prepared_queue_iteration_path.is_file() else {}
        )
        prepared_queue_iteration_markdown = (
            prepared_queue_iteration_dir / "versions" / "current-baseline.md"
        ).read_text() if (prepared_queue_iteration_dir / "versions" / "current-baseline.md").is_file() else ""
        manual_queue_dir = tmpdir / "manual-prepared-queue"
        (manual_queue_dir / ".kubeactuary").mkdir(parents=True)
        (manual_queue_dir / ".kubeactuary" / "live-validation-queue.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "kube-actuary.live-validation-queue.v1",
                    "source": "docs/release-taskboard.md",
                    "mode": "inventory-only",
                    "clusterWrites": "disabled",
                    "summary": {
                        "total": 2,
                        "toolReady": 0,
                        "blockedByTools": 1,
                        "blockedByEnvironment": 1,
                        "missingTools": ["kind"],
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
                            "commands": [
                                "python3 -B scripts/capture_controller_resource_budget.py --output <kubectl-top-output.txt> --run",
                            ],
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
                        },
                    ],
                    "closureCommands": [],
                }
            )
            + "\n"
        )
        manual_queue_worklist_markdown = run_generator(
            "--format",
            "markdown",
            "--open-only",
            "--evidence-dir",
            str(manual_queue_dir),
        )
        next_task_output = tmpdir / "next-task.json"
        written_next_task = run_select("--format", "json", "--output", str(next_task_output))
        next_task_output_written = next_task_output.is_file()
        completed_evidence_dir = tmpdir / "completed-evidence"
        (completed_evidence_dir / "raw").mkdir(parents=True)
        (completed_evidence_dir / "supplemental").mkdir()
        (completed_evidence_dir / ".kubeactuary").mkdir()
        (completed_evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt").write_text(
            "POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n"
        )
        (completed_evidence_dir / "supplemental" / "01-controller-resource-budget-external-2.json").write_text("{}\n")
        (completed_evidence_dir / ".kubeactuary" / "version-iteration-advance.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "kube-actuary.version-iteration-advance.v1",
                    "mode": "run",
                    "status": "passed",
                    "queueSource": "prepared-live-validation-queue",
                    "runId": "after-evidence-advance",
                    "createdAt": "2026-07-06T00:03:00+00:00",
                    "runner": {
                        "mode": "run",
                        "status": "passed",
                        "summary": {
                            "commands": 2,
                            "validCommands": 2,
                            "ran": 2,
                            "failed": 0,
                        },
                    },
                    "nextTask": {
                        "selected": "01-controller-resource-budget",
                        "captureStatus": "tool-ready",
                        "nextStep": "capture evidence with the listed commands",
                        "skippedCompleteEvidence": 1,
                        "worklistCommands": [
                            "python3 -B scripts/generate_version_worklist.py --format markdown --open-only --version 'Current Baseline' --capture-status tool-ready",
                        ],
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        (completed_evidence_dir / ".kubeactuary" / "next-unblock-action.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "kube-actuary.next-unblock-action.v1",
                    "sourceWorklistQueueSource": "prepared-live-validation-queue",
                    "source": "docs/roadmap.md",
                    "status": "selected",
                    "planStatus": "blocked",
                    "clusterWrites": "disabled",
                    "selectionPolicy": "highest-items-then-kind-target",
                    "summary": {
                        "candidateActions": 1,
                        "blockedItems": 5,
                        "affectedVersions": 2,
                        "selected": True,
                        "selectedActionId": "01-missing-tool-kind",
                        "selectedKind": "missing-tool",
                        "selectedTarget": "kind",
                        "selectedItems": 5,
                    },
                    "selected": {
                        "id": "01-missing-tool-kind",
                        "kind": "missing-tool",
                        "tool": "kind",
                        "items": 5,
                        "affectedVersions": ["0.2.0", "0.3.0"],
                        "nextStep": "install kind or run the verifier on a host that has kind",
                        "commands": {
                            "verify": ["kind version"],
                            "refresh": [
                                "python3 -B scripts/prepare_live_evidence_directory.py "
                                + completed_evidence_dir.as_posix()
                            ],
                        },
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        (completed_evidence_dir / ".kubeactuary" / "next-unblock-action-run.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "kube-actuary.next-unblock-action-run.v1",
                    "mode": "run",
                    "status": "blocked",
                    "clusterWrites": "disabled",
                    "ranAt": "2026-07-06T00:03:10+00:00",
                    "evidenceDir": completed_evidence_dir.as_posix(),
                    "nextUnblockAction": {
                        "schemaVersion": "kube-actuary.next-unblock-action.v1",
                        "queueSource": "prepared-live-validation-queue",
                        "path": (completed_evidence_dir / ".kubeactuary" / "next-unblock-action.json").as_posix(),
                        "selected": {
                            "id": "01-missing-tool-kind",
                            "kind": "missing-tool",
                            "target": "kind",
                            "tool": "kind",
                            "items": 5,
                            "affectedVersions": ["0.2.0", "0.3.0"],
                            "nextStep": "install kind or run the verifier on a host that has kind",
                        },
                    },
                    "summary": {
                        "commands": 1,
                        "validCommands": 1,
                        "ran": 1,
                        "failed": 1,
                        "validationErrors": 0,
                    },
                    "validations": [
                        {
                            "index": 1,
                            "command": "kind version",
                            "normalized": ["kind", "version"],
                            "valid": True,
                            "errors": [],
                        }
                    ],
                    "records": [
                        {
                            "command": "kind version",
                            "stdout": "",
                            "stderr": "kind missing in test",
                            "exitCode": 127,
                            "ok": False,
                        }
                    ],
                    "failure": {
                        "command": "kind version",
                        "exitCode": 127,
                        "message": "kind missing in test",
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        evidence_worklist_result = run_generator(
            "--format",
            "json",
            "--open-only",
            "--evidence-dir",
            str(completed_evidence_dir),
        )
        evidence_worklist_markdown = run_generator(
            "--format",
            "markdown",
            "--open-only",
            "--evidence-dir",
            str(completed_evidence_dir),
        )
        evidence_iteration_dir = tmpdir / "evidence-iteration"
        evidence_iteration_result = run_prepare(
            str(evidence_iteration_dir),
            "--version",
            "Current Baseline",
            "--evidence-dir",
            str(completed_evidence_dir),
        )
        evidence_iteration_path = evidence_iteration_dir / "versions" / "current-baseline.json"
        evidence_iteration_payload = (
            json.loads(evidence_iteration_path.read_text()) if evidence_iteration_path.is_file() else {}
        )
        evidence_iteration_markdown_path = evidence_iteration_dir / "versions" / "current-baseline.md"
        evidence_iteration_markdown = (
            evidence_iteration_markdown_path.read_text() if evidence_iteration_markdown_path.is_file() else ""
        )
        skipped_complete_task = run_select(
            "--format",
            "json",
            "--evidence-dir",
            str(completed_evidence_dir),
            "--skip-complete-evidence",
        )
        skipped_complete_text = run_select(
            "--evidence-dir",
            str(completed_evidence_dir),
            "--skip-complete-evidence",
        )
        iteration_dir = tmpdir / "iteration"
        iteration_result = run_prepare(
            str(iteration_dir),
            "--version",
            "0.4.3",
            "--open-only",
        )
        iteration_paths = (
            iteration_dir / "README.md",
            iteration_dir / "worklist.json",
            iteration_dir / "worklist.md",
            iteration_dir / "versions" / "0-4-3.json",
            iteration_dir / "versions" / "0-4-3.md",
        )
        iteration_files_present = {path.name: path.is_file() for path in iteration_paths}
        iteration_payload_path = iteration_dir / "versions" / "0-4-3.json"
        iteration_payload = json.loads(iteration_payload_path.read_text()) if iteration_payload_path.is_file() else {}
        iteration_markdown_path = iteration_dir / "versions" / "0-4-3.md"
        iteration_markdown_text = iteration_markdown_path.read_text() if iteration_markdown_path.is_file() else ""
        filtered_iteration_dir = tmpdir / "filtered-iteration"
        filtered_iteration_result = run_prepare(
            str(filtered_iteration_dir),
            "--open-only",
            "--missing-tool",
            "kind",
        )
        filtered_iteration_worklist_path = filtered_iteration_dir / "worklist.json"
        filtered_iteration_worklist = (
            json.loads(filtered_iteration_worklist_path.read_text()) if filtered_iteration_worklist_path.is_file() else {}
        )
        filtered_iteration_readme = (
            filtered_iteration_dir / "README.md"
        ).read_text() if (filtered_iteration_dir / "README.md").is_file() else ""
        filtered_iteration_044_path = (
            filtered_iteration_dir / "versions" / "0-4-4.md"
        )
        filtered_iteration_044_markdown = (
            filtered_iteration_044_path.read_text()
            if filtered_iteration_044_path.is_file()
            else ""
        )
        filtered_iteration_044_worklist = (
            "worklist: `python3 -B scripts/generate_version_worklist.py "
            "--format markdown --open-only --version 0.4.4 "
            "--capture-status missing-tools --missing-tool kind`"
        )
        probe_iteration_dir = tmpdir / "probe-iteration"
        probe_iteration_result = run_prepare(
            str(probe_iteration_dir),
            "--version",
            "0.4.3",
            "--open-only",
            "--probe-environment",
            env=probe_env,
        )
        probe_iteration_path = probe_iteration_dir / "versions" / "0-4-3.json"
        probe_iteration_payload = json.loads(probe_iteration_path.read_text()) if probe_iteration_path.is_file() else {}
        compare_result = run_compare(str(iteration_dir), str(probe_iteration_dir), "--format", "json")
        compare_payload = json.loads(compare_result.stdout) if compare_result.returncode == 0 else {}
        markdown_compare = run_compare(str(iteration_dir), str(probe_iteration_dir), "--format", "markdown")
        diff_output = tmpdir / "iteration-diff.json"
        written_compare = run_compare(str(iteration_dir), str(probe_iteration_dir), "--output", str(diff_output))
        diff_output_written = diff_output.is_file()
        history_dir = tmpdir / "history"
        first_record = run_record(
            str(history_dir),
            "--run-id",
            "before",
            "--created-at",
            "2026-07-06T00:00:00+00:00",
            "--version",
            "0.4.3",
        )
        second_record = run_record(
            str(history_dir),
            "--run-id",
            "after",
            "--created-at",
            "2026-07-06T00:01:00+00:00",
            "--version",
            "0.4.3",
            "--probe-environment",
            env=probe_env,
        )
        repeated_history_dir = tmpdir / "repeated-history"
        repeated_first_record = run_record(
            str(repeated_history_dir),
            "--run-id",
            "blocked-one",
            "--created-at",
            "2026-07-06T00:01:10+00:00",
            "--version",
            "0.4.3",
            "--probe-environment",
            env=probe_env,
        )
        repeated_second_record = run_record(
            str(repeated_history_dir),
            "--run-id",
            "blocked-two",
            "--created-at",
            "2026-07-06T00:01:20+00:00",
            "--version",
            "0.4.3",
            "--probe-environment",
            env=probe_env,
        )
        evidence_history_dir = tmpdir / "evidence-history"
        evidence_history_before = run_record(
            str(evidence_history_dir),
            "--run-id",
            "before-evidence",
            "--created-at",
            "2026-07-06T00:02:00+00:00",
            "--version",
            "Current Baseline",
        )
        evidence_history_after = run_record(
            str(evidence_history_dir),
            "--run-id",
            "after-evidence",
            "--created-at",
            "2026-07-06T00:03:00+00:00",
            "--version",
            "Current Baseline",
            "--evidence-dir",
            str(completed_evidence_dir),
        )
        history_index_path = history_dir / "index.json"
        history_index = json.loads(history_index_path.read_text()) if history_index_path.is_file() else {}
        history_readme_text = (history_dir / "README.md").read_text() if (history_dir / "README.md").is_file() else ""
        history_diff_path = history_dir / "runs" / "after" / "diff-from-previous.json"
        history_diff = json.loads(history_diff_path.read_text()) if history_diff_path.is_file() else {}
        history_status = run_inspect_history(str(history_dir))
        history_status_json = run_inspect_history(str(history_dir), "--format", "json")
        history_status_markdown = run_inspect_history(str(history_dir), "--format", "markdown")
        history_status_payload = json.loads(history_status_json.stdout) if history_status_json.returncode == 0 else {}
        history_status_markdown_worklist = (
            "worklist: `python3 -B scripts/generate_version_worklist.py "
            "--format markdown --open-only --version 0.4.3 "
            "--capture-status blocked-by-environment "
            "--environment-status cluster-unavailable`"
        )
        history_status_record_command = (
            f"python3 -B scripts/inspect_version_history.py {history_dir.as_posix()} --record"
        )
        history_status_iteration_command = (
            f"python3 -B scripts/record_version_iteration.py {history_dir.as_posix()} "
            "--version 0.4.3 --probe-environment"
        )
        history_status_run_path = (history_dir / "runs" / "after").as_posix()
        history_status_worklist_path = (history_dir / "runs" / "after" / "worklist.json").as_posix()
        history_status_diff_path = history_diff_path.as_posix()
        history_status_output = tmpdir / "history-status.json"
        written_history_status = run_inspect_history(
            str(history_dir),
            "--format",
            "json",
            "--output",
            str(history_status_output),
        )
        history_status_output_written = history_status_output.is_file()
        recorded_history_status = run_inspect_history(
            str(history_dir),
            "--format",
            "json",
            "--record",
        )
        history_status_record_json = history_dir / "status.json"
        history_status_record_md = history_dir / "status.md"
        history_status_record_payload = (
            json.loads(history_status_record_json.read_text())
            if history_status_record_json.is_file()
            else {}
        )
        history_status_record_md_text = (
            history_status_record_md.read_text()
            if history_status_record_md.is_file()
            else ""
        )
        repeated_history_status = run_inspect_history(str(repeated_history_dir), "--format", "json")
        repeated_history_status_payload = (
            json.loads(repeated_history_status.stdout) if repeated_history_status.returncode == 0 else {}
        )
        repeated_history_status_text = run_inspect_history(str(repeated_history_dir))
        repeated_history_status_markdown = run_inspect_history(str(repeated_history_dir), "--format", "markdown")
        history_context_worklist = run_generator(
            "--format",
            "json",
            "--open-only",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--history-dir",
            str(repeated_history_dir),
            env=probe_env,
        )
        history_context_worklist_payload = (
            json.loads(history_context_worklist.stdout) if history_context_worklist.returncode == 0 else {}
        )
        history_context_worklist_text = run_generator(
            "--format",
            "text",
            "--open-only",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--history-dir",
            str(repeated_history_dir),
            env=probe_env,
        )
        history_context_worklist_markdown = run_generator(
            "--format",
            "markdown",
            "--open-only",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--history-dir",
            str(repeated_history_dir),
            env=probe_env,
        )
        history_context_next_task = run_select(
            "--format",
            "json",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--history-dir",
            str(repeated_history_dir),
            env=probe_env,
        )
        history_context_next_task_payload = (
            json.loads(history_context_next_task.stdout) if history_context_next_task.returncode == 0 else {}
        )
        history_context_next_task_text = run_select(
            "--format",
            "text",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--history-dir",
            str(repeated_history_dir),
            env=probe_env,
        )
        history_context_next_task_markdown = run_select(
            "--format",
            "markdown",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--history-dir",
            str(repeated_history_dir),
            env=probe_env,
        )
        history_context_runnable_only_next_task = run_select(
            "--format",
            "json",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--history-dir",
            str(repeated_history_dir),
            "--runnable-only",
            env=probe_env,
        )
        history_context_runnable_only_text = run_select(
            "--format",
            "text",
            "--version",
            "0.4.3",
            "--probe-environment",
            "--history-dir",
            str(repeated_history_dir),
            "--runnable-only",
            env=probe_env,
        )
        history_context_runnable_only_payload = (
            json.loads(history_context_runnable_only_next_task.stdout)
            if history_context_runnable_only_next_task.returncode == 0
            else {}
        )
        evidence_history_index_path = evidence_history_dir / "index.json"
        evidence_history_index = (
            json.loads(evidence_history_index_path.read_text()) if evidence_history_index_path.is_file() else {}
        )
        evidence_history_readme = (
            evidence_history_dir / "README.md"
        ).read_text() if (evidence_history_dir / "README.md").is_file() else ""
        evidence_history_diff_path = evidence_history_dir / "runs" / "after-evidence" / "diff-from-previous.json"
        evidence_history_diff = (
            json.loads(evidence_history_diff_path.read_text()) if evidence_history_diff_path.is_file() else {}
        )
        evidence_history_status = run_inspect_history(str(evidence_history_dir), "--format", "json")
        evidence_history_status_payload = (
            json.loads(evidence_history_status.stdout) if evidence_history_status.returncode == 0 else {}
        )
        evidence_history_status_text = run_inspect_history(str(evidence_history_dir))
        evidence_history_status_markdown = run_inspect_history(str(evidence_history_dir), "--format", "markdown")
        stale_advance_path = completed_evidence_dir / ".kubeactuary" / "version-iteration-advance.json"
        stale_advance_payload = json.loads(stale_advance_path.read_text()) if stale_advance_path.is_file() else {}
        stale_advance_payload.setdefault("nextTask", {})["selected"] = "stale-task"
        stale_advance_payload.setdefault("nextTask", {})["captureStatus"] = "missing-tools"
        stale_advance_path.write_text(json.dumps(stale_advance_payload, indent=2, sort_keys=True) + "\n")
        stale_evidence_history_status = run_inspect_history(str(evidence_history_dir), "--format", "json")
        stale_evidence_history_status_payload = (
            json.loads(stale_evidence_history_status.stdout) if stale_evidence_history_status.returncode == 0 else {}
        )
        stale_evidence_history_status_text = run_inspect_history(str(evidence_history_dir))
        prepared_history_dir = tmpdir / "prepared-history"
        prepared_history_record = run_record(
            str(prepared_history_dir),
            "--run-id",
            "prepared",
            "--created-at",
            "2026-07-06T00:04:00+00:00",
            "--open-only",
            "--evidence-dir",
            str(prepared_queue_dir),
        )
        prepared_history_index_path = prepared_history_dir / "index.json"
        prepared_history_index = (
            json.loads(prepared_history_index_path.read_text()) if prepared_history_index_path.is_file() else {}
        )
        prepared_history_readme = (
            prepared_history_dir / "README.md"
        ).read_text() if (prepared_history_dir / "README.md").is_file() else ""
        prepared_history_status = run_inspect_history(str(prepared_history_dir), "--format", "json")
        prepared_history_status_payload = (
            json.loads(prepared_history_status.stdout) if prepared_history_status.returncode == 0 else {}
        )
        filtered_history_dir = tmpdir / "filtered-history"
        filtered_history_record = run_record(
            str(filtered_history_dir),
            "--run-id",
            "kind-filter",
            "--created-at",
            "2026-07-06T00:05:00+00:00",
            "--open-only",
            "--missing-tool",
            "kind",
        )
        filtered_history_index_path = filtered_history_dir / "index.json"
        filtered_history_index = (
            json.loads(filtered_history_index_path.read_text()) if filtered_history_index_path.is_file() else {}
        )

    worklist = parse_worklist("json worklist", json_result, errors)
    single_version = parse_worklist("single-version worklist", single_version_result, errors)
    multi_version = parse_worklist("multi-version worklist", multi_version_result, errors)
    open_only = parse_worklist("open-only worklist", open_only_result, errors)
    filtered_missing_status = parse_worklist("capture-status filtered worklist", filtered_missing_status_result, errors)
    filtered_kind = parse_worklist("missing-tool filtered worklist", filtered_kind_result, errors)
    probe_worklist = parse_worklist("probe worklist", probe_result, errors)
    if markdown_result.returncode != 0:
        errors.append(f"markdown worklist failed: {markdown_result.stderr.strip() or markdown_result.stdout.strip()}")
    else:
        for snippet in (
            "missing-tool-blocker: `minikube`",
            "missing-tool-blocker: `az`",
            "missing-tool-blocker: `gcloud`",
            "worklist: `python3 -B scripts/generate_version_worklist.py --format markdown --open-only --capture-status missing-tools --missing-tool kind`",
            "blocker-worklist: `python3 -B scripts/generate_version_worklist.py --format markdown --open-only --version 0.4.4 --capture-status missing-tools --missing-tool kind`",
            "blockers: tools=`helm:2, kind:2, kubectl-krew:2, az:1, gcloud:1, k3s:1, microk8s:1, minikube:1`",
        ):
            if snippet not in markdown_result.stdout:
                errors.append(f"markdown worklist must include all blocker summaries: {snippet}")
    if text_result.returncode != 0:
        errors.append(f"text worklist failed: {text_result.stderr.strip() or text_result.stdout.strip()}")
    else:
        for snippet in (
            f"schema: {SCHEMA}",
            "open-items: 16",
            "capture-ready: 4",
            "missing-tool-blocker: kind (5 items)",
            "worklist: python3 -B scripts/generate_version_worklist.py --format markdown --open-only --capture-status missing-tools --missing-tool kind",
            "version: Current Baseline capture-ready",
            "item: Current Baseline tool-ready Controller resource budget",
            "closure-command: python3 -B scripts/validate_live_evidence.py <evidence.json> [...]",
        ):
            if snippet not in text_result.stdout:
                errors.append(f"text worklist must include local task detail: {snippet}")
    if prepared_queue.returncode != 0:
        errors.append(f"prepared live queue failed: {prepared_queue.stderr.strip() or prepared_queue.stdout.strip()}")
        prepared_queue_worklist = {}
        prepared_queue_next = {}
        prepared_environment_filter = {}
        prepared_environment_reason_filter = {}
        prepared_capture_filter = {}
    else:
        prepared_queue_worklist = parse_worklist("prepared queue worklist", prepared_queue_worklist_result, errors)
        prepared_queue_next = parse_worklist("prepared queue next task", prepared_queue_next_task, errors)
        prepared_environment_filter = parse_worklist(
            "prepared environment filtered worklist",
            prepared_environment_filter_result,
            errors,
        )
        prepared_environment_reason_filter = parse_worklist(
            "prepared environment-reason filtered worklist",
            prepared_environment_reason_filter_result,
            errors,
        )
        prepared_capture_filter = parse_worklist(
            "prepared capture-status filtered worklist",
            prepared_capture_filter_result,
            errors,
        )
        if (
            prepared_queue_worklist_markdown.returncode != 0
            or "Queue source: `prepared-live-validation-queue`" not in prepared_queue_worklist_markdown.stdout
        ):
            errors.append("prepared queue worklist Markdown must show prepared queue source")
        if manual_queue_worklist_markdown.returncode != 0:
            errors.append(
                "manual prepared queue worklist Markdown failed: "
                f"{manual_queue_worklist_markdown.stderr.strip() or manual_queue_worklist_markdown.stdout.strip()}"
            )
        for snippet in (
            "missing tools: `kind`",
            "next: start or select a disposable cluster, then rerun the probe",
            "next: install missing tools or run on a host that has them",
        ):
            if snippet not in manual_queue_worklist_markdown.stdout:
                errors.append(f"manual prepared queue worklist Markdown missing item detail: {snippet}")
        if (
            prepared_queue_next_markdown.returncode != 0
            or "Queue source: `prepared-live-validation-queue`" not in prepared_queue_next_markdown.stdout
        ):
            errors.append("prepared queue next-task Markdown must show prepared queue source")
        if prepared_queue_iteration.returncode != 0:
            errors.append(
                "prepared queue iteration failed: "
                f"{prepared_queue_iteration.stderr.strip() or prepared_queue_iteration.stdout.strip()}"
            )
        if "Queue source: `prepared-live-validation-queue`" not in prepared_queue_iteration_readme:
            errors.append("prepared queue iteration index must show prepared queue source")
        if prepared_queue_iteration_payload.get("sourceWorklistQueueSource") != "prepared-live-validation-queue":
            errors.append("prepared queue iteration JSON must preserve queue source")
        if "Queue source: `prepared-live-validation-queue`" not in prepared_queue_iteration_markdown:
            errors.append("prepared queue iteration Markdown must show prepared queue source")
    next_task = parse_worklist("next task", next_task_result, errors)
    next_task_filtered = parse_worklist("filtered next task", next_task_version, errors)
    next_task_tool_blocked = parse_worklist("tool-blocked next task", next_task_missing, errors)
    next_task_kind_payload = parse_worklist("missing-tool filtered next task", next_task_kind, errors)
    next_task_with_paths = parse_worklist("path-resolved next task", next_task_paths, errors)
    next_task_runnable_only_payload = parse_worklist("runnable-only next task", next_task_runnable_only, errors)
    next_task_blocked_only_payload = parse_worklist("blocked-only next task", next_task_blocked_only, errors)
    probe_next_task_payload = parse_worklist("probe next task", probe_next_task, errors)
    evidence_worklist = parse_worklist("evidence-aware worklist", evidence_worklist_result, errors)
    skipped_complete_payload = parse_worklist("skip-complete next task", skipped_complete_task, errors)
    if markdown_result.returncode != 0:
        errors.append(f"markdown worklist failed: {markdown_result.stderr.strip() or markdown_result.stdout.strip()}")
    if "# KubeActuary Version Worklist" not in markdown_result.stdout:
        errors.append("markdown worklist missing heading")
    if filtered_kind_markdown.returncode != 0 or "missing-tools: `kind`" not in filtered_kind_markdown.stdout:
        errors.append("missing-tool filtered worklist markdown must show active filter")
    if written.returncode != 0 or not output_written:
        errors.append("worklist generator must write requested output file")
    if next_task_markdown.returncode != 0 or "# KubeActuary Next Version Task" not in next_task_markdown.stdout:
        errors.append("next task selector markdown must render")
    if evidence_worklist_markdown.returncode != 0 or "evidence: `3/3`" not in evidence_worklist_markdown.stdout:
        errors.append("evidence-aware worklist markdown must render file readiness")
    if written_next_task.returncode != 0 or not next_task_output_written:
        errors.append("next task selector must write requested output file")
    if skipped_complete_text.returncode != 0 or "evidence-files: 0/5" not in skipped_complete_text.stdout:
        errors.append("skip-complete next task text must report selected evidence file readiness")
    if iteration_result.returncode != 0:
        errors.append(f"version iteration pack failed: {iteration_result.stderr.strip() or iteration_result.stdout.strip()}")
    if filtered_iteration_result.returncode != 0:
        errors.append(
            f"filtered version iteration pack failed: "
            f"{filtered_iteration_result.stderr.strip() or filtered_iteration_result.stdout.strip()}"
        )
    if evidence_iteration_result.returncode != 0:
        errors.append(
            f"evidence-aware version iteration failed: "
            f"{evidence_iteration_result.stderr.strip() or evidence_iteration_result.stdout.strip()}"
        )
    for name, present in iteration_files_present.items():
        if not present:
            errors.append(f"version iteration pack missing file: {name}")
    if iteration_payload.get("schemaVersion") != ITERATION_SCHEMA:
        errors.append("version iteration schemaVersion mismatch")
    if iteration_payload.get("version") != "0.4.3" or iteration_payload.get("status") != "capture-ready":
        errors.append("version iteration should capture 0.4.3 as capture-ready")
    if iteration_payload.get("summary", {}).get("open") != 1:
        errors.append("version iteration should preserve open item count")
    if iteration_markdown_text and "Resource budget target" not in iteration_markdown_text:
        errors.append("version iteration markdown must include the target open item")
    if filtered_iteration_worklist.get("summary", {}).get("openItems") != 5:
        errors.append("filtered version iteration should keep five kind-blocked items")
    if filtered_iteration_worklist.get("filters", {}).get("missingTools") != ["kind"]:
        errors.append("filtered version iteration should preserve missing-tool filters")
    if "missing-tools: `kind`" not in filtered_iteration_readme:
        errors.append("filtered version iteration README should show active filter")
    if "missing-tool-blocker: `kind`" not in filtered_iteration_044_markdown:
        errors.append("filtered version iteration Markdown should show blocker summaries")
    if filtered_iteration_044_worklist not in filtered_iteration_044_markdown:
        errors.append("filtered version iteration Markdown should show version-scoped blocker drilldown")
    if evidence_iteration_payload.get("evidenceDir") != str(completed_evidence_dir):
        errors.append("evidence-aware iteration should record the evidence directory")
    evidence_iteration_summary = evidence_iteration_payload.get("summary", {})
    if evidence_iteration_summary.get("completeEvidenceItems") != 1:
        errors.append("evidence-aware iteration should preserve completed evidence item count")
    evidence_iteration_items = evidence_iteration_payload.get("openItems", [])
    evidence_iteration_resource_item = next(
        (item for item in evidence_iteration_items if item.get("id") == "01-controller-resource-budget"),
        {},
    )
    if evidence_iteration_resource_item.get("evidenceSummary", {}).get("complete") is not True:
        errors.append("evidence-aware iteration should preserve complete item evidence summary")
    if not evidence_iteration_payload.get("resolvedClosureCommands"):
        errors.append("evidence-aware iteration should preserve resolved closure commands")
    evidence_iteration_unblock = evidence_iteration_payload.get("nextUnblockAction") or {}
    if evidence_iteration_unblock.get("selected", {}).get("id") != "01-missing-tool-kind":
        errors.append("evidence-aware iteration should preserve selected next-unblock action")
    if evidence_iteration_unblock.get("selected", {}).get("target") != "kind":
        errors.append("evidence-aware iteration should preserve selected next-unblock target")
    evidence_iteration_unblock_run = evidence_iteration_payload.get("nextUnblockActionRun") or {}
    if evidence_iteration_unblock_run.get("status") != "blocked":
        errors.append("evidence-aware iteration should preserve next-unblock runner status")
    if (evidence_iteration_unblock_run.get("failure") or {}).get("message") != "kind missing in test":
        errors.append("evidence-aware iteration should preserve next-unblock runner failure")
    if "evidence: `3/3`" not in evidence_iteration_markdown:
        errors.append("evidence-aware iteration markdown must render evidence readiness")
    if "## Next Unblock Action" not in evidence_iteration_markdown:
        errors.append("evidence-aware iteration markdown must render next-unblock action details")
    if "## Next Unblock Action Run" not in evidence_iteration_markdown:
        errors.append("evidence-aware iteration markdown must render next-unblock runner details")
    if probe_iteration_result.returncode != 0:
        errors.append(
            f"probe version iteration failed: {probe_iteration_result.stderr.strip() or probe_iteration_result.stdout.strip()}"
        )
    if probe_iteration_payload.get("status") != "blocked-by-environment":
        errors.append("probe version iteration should capture environment blocker")
    if probe_iteration_payload.get("summary", {}).get("blockedByEnvironment") != 1:
        errors.append("probe version iteration should preserve environment blocker count")
    if compare_result.returncode != 0:
        errors.append(f"version iteration diff failed: {compare_result.stderr.strip() or compare_result.stdout.strip()}")
    if compare_payload.get("schemaVersion") != DIFF_SCHEMA:
        errors.append("version iteration diff schemaVersion mismatch")
    compare_summary = compare_payload.get("summary", {})
    if compare_summary.get("statusChanged") != 1:
        errors.append("version iteration diff should record one status change")
    if compare_summary.get("captureReadyDelta") != -1:
        errors.append("version iteration diff should record capture-ready delta")
    if compare_summary.get("blockedByEnvironmentDelta") != 1:
        errors.append("version iteration diff should record environment blocker delta")
    if compare_summary.get("changedItems") != 1:
        errors.append("version iteration diff should record one changed item")
    if markdown_compare.returncode != 0 or "# KubeActuary Version Iteration Diff" not in markdown_compare.stdout:
        errors.append("version iteration diff markdown must render")
    if written_compare.returncode != 0 or not diff_output_written:
        errors.append("version iteration diff must write requested output file")
    if first_record.returncode != 0:
        errors.append(f"first version iteration history failed: {first_record.stderr.strip() or first_record.stdout.strip()}")
    if second_record.returncode != 0:
        errors.append(f"second version iteration history failed: {second_record.stderr.strip() or second_record.stdout.strip()}")
    if evidence_history_before.returncode != 0:
        errors.append(
            f"first evidence-aware history failed: "
            f"{evidence_history_before.stderr.strip() or evidence_history_before.stdout.strip()}"
        )
    if evidence_history_after.returncode != 0:
        errors.append(
            f"second evidence-aware history failed: "
            f"{evidence_history_after.stderr.strip() or evidence_history_after.stdout.strip()}"
        )
    if history_index.get("schemaVersion") != HISTORY_SCHEMA:
        errors.append("version iteration history schemaVersion mismatch")
    if len(history_index.get("runs", [])) != 2:
        errors.append("version iteration history should record two runs")
    second_run = history_index.get("runs", [{}])[-1] if history_index.get("runs") else {}
    if second_run.get("previousRunId") != "before":
        errors.append("version iteration history should link to previous run")
    if second_run.get("diffSummary", {}).get("blockedByEnvironmentDelta") != 1:
        errors.append("version iteration history should preserve diff summary")
    if history_diff.get("schemaVersion") != DIFF_SCHEMA:
        errors.append("version iteration history should write diff artifact")
    if "after" not in history_readme_text or "blocked-by-environment-delta=1" not in history_readme_text:
        errors.append("version iteration history README should summarize runs and diff")
    if history_status.returncode != 0 or "version-iteration-history-status: valid" not in history_status.stdout:
        errors.append("version iteration history inspector text must pass")
    if history_status_payload.get("schemaVersion") != HISTORY_STATUS_SCHEMA:
        errors.append("version iteration history status schemaVersion mismatch")
    status_summary = history_status_payload.get("summary", {})
    if status_summary.get("runs") != 2 or status_summary.get("latestRunId") != "after":
        errors.append("version iteration history status should report latest run")
    if status_summary.get("blockedByEnvironment") != 1 or status_summary.get("diffs") != 1:
        errors.append("version iteration history status should summarize latest blockers and diffs")
    latest_diff_summary = history_status_payload.get("latestDiffSummary", {})
    if latest_diff_summary.get("statusChanged") != 1:
        errors.append("version iteration history status should preserve latest diff status changes")
    if latest_diff_summary.get("blockedByEnvironmentDelta") != 1:
        errors.append("version iteration history status should preserve latest environment delta")
    latest_artifacts = history_status_payload.get("latestArtifacts", {})
    if latest_artifacts.get("runPath") != history_status_run_path:
        errors.append("version iteration history status should show latest run artifact path")
    if latest_artifacts.get("worklistPath") != history_status_worklist_path:
        errors.append("version iteration history status should show latest worklist artifact path")
    if latest_artifacts.get("diffPath") != history_status_diff_path:
        errors.append("version iteration history status should show latest diff artifact path")
    latest_filters = history_status_payload.get("latestFilters", {})
    if latest_filters.get("versions") != ["0.4.3"]:
        errors.append("version iteration history status should show latest version filters")
    if latest_filters.get("openOnly") is not False:
        errors.append("version iteration history status should show latest open-only filter")
    if latest_filters.get("probeEnvironment") is not True:
        errors.append("version iteration history status should show latest probe filter")
    if latest_filters.get("kubectl") != "kubectl":
        errors.append("version iteration history status should show latest kubectl filter")
    latest_next_task = history_status_payload.get("latestNextTask", {})
    if latest_next_task.get("version") != "0.4.3":
        errors.append("version iteration history status should show latest next-task version")
    if latest_next_task.get("id") != "11-resource-budget-target-idle-50m-cpu-and-64mi-memory":
        errors.append("version iteration history status should show latest next-task id")
    if latest_next_task.get("captureStatus") != "blocked-by-environment":
        errors.append("version iteration history status should show latest next-task capture status")
    if latest_next_task.get("kind") != "controller-resource-budget":
        errors.append("version iteration history status should show latest next-task kind")
    if not latest_next_task.get("commands"):
        errors.append("version iteration history status should preserve latest next-task commands")
    latest_version_diffs = history_status_payload.get("latestVersionDiffs", [])
    latest_version_diff = next(
        (item for item in latest_version_diffs if item.get("version") == "0.4.3"),
        {},
    )
    latest_version_delta = latest_version_diff.get("summaryDelta", {})
    if latest_version_diff.get("beforeStatus") != "capture-ready":
        errors.append("version iteration history status should preserve latest version before status")
    if latest_version_diff.get("afterStatus") != "blocked-by-environment":
        errors.append("version iteration history status should preserve latest version after status")
    if latest_version_delta.get("captureReady") != -1:
        errors.append("version iteration history status should preserve latest version capture-ready delta")
    if latest_version_delta.get("blockedByEnvironment") != 1:
        errors.append("version iteration history status should preserve latest version environment delta")
    if len(latest_version_diff.get("changedItems", [])) != 1:
        errors.append("version iteration history status should preserve latest version changed items")
    history_next_commands = history_status_payload.get("nextCommands", [])
    for command in (history_status_record_command, history_status_iteration_command):
        if command not in history_next_commands:
            errors.append(f"version iteration history status should show next command: {command}")
    latest_history_probe = history_status_payload.get("latestEnvironmentProbe", {})
    if latest_history_probe.get("clusterAccess") != "unavailable":
        errors.append("version iteration history status should preserve latest probe cluster access")
    if latest_history_probe.get("reason") != "command-failed":
        errors.append("version iteration history status should preserve latest probe reason")
    failed_probe_checks = latest_history_probe.get("failedChecks", [])
    if not any(
        item.get("name") == "cluster-info"
        and item.get("exitCode") == 1
        and item.get("reason") == "command-failed"
        and item.get("message") == "cluster unavailable from fake kubectl"
        for item in failed_probe_checks
    ):
        errors.append("version iteration history status should summarize failed probe reasons and messages")
    latest_history_blockers = history_status_payload.get("latestBlockers", {})
    if not any(
        item.get("status") == "cluster-unavailable" and item.get("items") == 1
        for item in latest_history_blockers.get("environment", [])
    ):
        errors.append("version iteration history status should preserve latest environment blockers")
    if not any(
        item.get("reason") == "command-failed" and item.get("items") == 1
        for item in latest_history_blockers.get("environmentReasons", [])
    ):
        errors.append("version iteration history status should preserve latest environment reason blockers")
    latest_history_next_task = history_status_payload.get("latestNextTask", {})
    if not any(
        "--version 0.4.3 --capture-status blocked-by-environment --environment-status cluster-unavailable" in command
        for command in latest_history_next_task.get("worklistCommands", [])
    ):
        errors.append("version iteration history status should preserve latest next-task worklist drilldown")
    if repeated_first_record.returncode != 0:
        errors.append(
            "repeated blocker history first record failed: "
            f"{repeated_first_record.stderr.strip() or repeated_first_record.stdout.strip()}"
        )
    if repeated_second_record.returncode != 0:
        errors.append(
            "repeated blocker history second record failed: "
            f"{repeated_second_record.stderr.strip() or repeated_second_record.stdout.strip()}"
        )
    repeated_blocker = repeated_history_status_payload.get("latestBlockerStreak") or {}
    repeated_signature = repeated_blocker.get("signature") or {}
    if repeated_blocker.get("streak") != 2 or repeated_blocker.get("status") != "repeated":
        errors.append("version iteration history status should report repeated latest blocker streak")
    if repeated_blocker.get("firstRunId") != "blocked-one" or repeated_blocker.get("latestRunId") != "blocked-two":
        errors.append("version iteration history status should preserve repeated blocker run ids")
    if repeated_signature.get("id") != "11-resource-budget-target-idle-50m-cpu-and-64mi-memory":
        errors.append("version iteration history status should preserve repeated blocker task id")
    if repeated_signature.get("environmentReason") != "command-failed":
        errors.append("version iteration history status should preserve repeated blocker reason")
    repeated_action = repeated_history_status_payload.get("latestBlockerAction") or {}
    if repeated_action.get("action") != "resolve-environment":
        errors.append("version iteration history status should summarize repeated blocker action")
    if repeated_action.get("retryRecommended") is not False:
        errors.append("version iteration history status should suppress retry before blocker resolution")
    if repeated_action.get("retryAfter") != "environment probe succeeds":
        errors.append("version iteration history status should explain when retry is useful")
    if repeated_action.get("nextStep") != "start or select a disposable cluster, then rerun the probe":
        errors.append("version iteration history status should preserve blocker next step")
    if not any("--environment-status cluster-unavailable" in command for command in repeated_action.get("worklistCommands", [])):
        errors.append("version iteration history status should include blocker action worklist commands")
    if "record_version_iteration.py" not in str(repeated_action.get("retryCommand")):
        errors.append("version iteration history status should preserve the latest-filter retry command")
    if history_context_worklist.returncode != 0:
        errors.append(
            "history-context worklist failed: "
            f"{history_context_worklist.stderr.strip() or history_context_worklist.stdout.strip()}"
        )
    history_context_item = (
        ((history_context_worklist_payload.get("versions") or [{}])[0].get("openItems") or [{}])[0]
        if history_context_worklist_payload.get("versions")
        else {}
    )
    history_context = history_context_item.get("historyContext") or {}
    if history_context.get("historyDir") != str(repeated_history_dir):
        errors.append("history-context worklist should preserve history directory")
    if history_context.get("latestBlockerStreak", {}).get("streak") != 2:
        errors.append("history-context worklist should attach latest blocker streak")
    if history_context.get("latestBlockerAction", {}).get("action") != "resolve-environment":
        errors.append("history-context worklist should attach latest blocker action")
    if history_context.get("latestBlockerAction", {}).get("retryRecommended") is not False:
        errors.append("history-context worklist should attach retry guard")
    for snippet in (
        "history-dir: ",
        "history-blocker-streak: 2",
        "history-blocker-status: repeated",
        "history-blocker-action: resolve-environment",
        "history-blocker-retry-recommended: false",
    ):
        if snippet not in history_context_worklist_text.stdout:
            errors.append(f"history-context worklist text should show history detail: {snippet}")
    for snippet in (
        "history-dir:",
        "history: `repeated` streak=2",
        "history-action: `resolve-environment`",
        "history-retry: `false`",
    ):
        if snippet not in history_context_worklist_markdown.stdout:
            errors.append(f"history-context worklist Markdown should show history detail: {snippet}")
    if history_context_next_task.returncode != 0:
        errors.append(
            "history-context next task failed: "
            f"{history_context_next_task.stderr.strip() or history_context_next_task.stdout.strip()}"
        )
    history_context_selected = history_context_next_task_payload.get("selected") or {}
    selected_history_context = history_context_selected.get("historyContext") or {}
    if history_context_next_task_payload.get("filters", {}).get("historyDir") != str(repeated_history_dir):
        errors.append("history-context next task should preserve history directory filter")
    if history_context_selected.get("runnable") is not False:
        errors.append("history-context blocked next task should be marked non-runnable")
    history_context_blocker = history_context_selected.get("blocker") or {}
    if history_context_blocker.get("message") != "environment reason: command-failed":
        errors.append("history-context blocked next task should explain the environment blocker")
    if not any(
        "--capture-status blocked-by-environment --environment-reason command-failed" in command
        for command in history_context_blocker.get("worklistCommands") or []
    ):
        errors.append("history-context blocked next task should include blocker worklist drilldown")
    if history_context_runnable_only_next_task.returncode != 0:
        errors.append(
            "history-context runnable-only next task failed: "
            f"{history_context_runnable_only_next_task.stderr.strip() or history_context_runnable_only_next_task.stdout.strip()}"
        )
    if history_context_runnable_only_payload.get("selected") is not None:
        errors.append("history-context runnable-only next task should not select blocked work")
    if history_context_runnable_only_payload.get("filters", {}).get("runnableOnly") is not True:
        errors.append("history-context runnable-only next task should preserve runnable-only filter")
    if history_context_runnable_only_payload.get("summary", {}).get("eligibleItems") != 0:
        errors.append("history-context runnable-only next task should report zero eligible runnable items")
    if history_context_runnable_only_payload.get("summary", {}).get("skippedNonRunnable") != 1:
        errors.append("history-context runnable-only next task should report one skipped non-runnable item")
    for snippet in (
        "next-version-task: none",
        "eligible-items: 0",
        "skipped-non-runnable: 1",
        "runnable-only: true",
    ):
        if snippet not in history_context_runnable_only_text.stdout:
            errors.append(f"history-context runnable-only next task text should show no runnable work: {snippet}")
    if selected_history_context.get("latestBlockerStreak", {}).get("streak") != 2:
        errors.append("history-context next task should attach latest blocker streak")
    if selected_history_context.get("latestBlockerAction", {}).get("action") != "resolve-environment":
        errors.append("history-context next task should attach latest blocker action")
    if selected_history_context.get("latestBlockerAction", {}).get("retryRecommended") is not False:
        errors.append("history-context next task should attach retry guard")
    for snippet in (
        "history-blocker-streak: 2",
        "history-blocker-status: repeated",
        "history-blocker-action: resolve-environment",
        "history-blocker-retry-recommended: false",
        "runnable: false",
        "blocker: environment reason: command-failed",
        "blocker-worklist: python3 -B scripts/generate_version_worklist.py",
        "blocked-command: python3 -B scripts/capture_controller_resource_budget.py",
    ):
        if snippet not in history_context_next_task_text.stdout:
            errors.append(f"history-context next task text should show history detail: {snippet}")
    for snippet in (
        "history: `repeated` streak=2",
        "history action: `resolve-environment`",
        "history retry: `false`",
        "runnable: `false`",
        "blocker: environment reason: command-failed",
        "blocker worklist: `python3 -B scripts/generate_version_worklist.py",
        "blocked command: `python3 -B scripts/capture_controller_resource_budget.py",
    ):
        if snippet not in history_context_next_task_markdown.stdout:
            errors.append(f"history-context next task Markdown should show history detail: {snippet}")
    for snippet in (
        "latest-blocker-streak: 2",
        "latest-blocker-status: repeated",
        "latest-blocker-first-run-id: blocked-one",
        "latest-blocker-latest-run-id: blocked-two",
        "latest-blocker-action: resolve-environment",
        "latest-blocker-retry-recommended: false",
        "latest-blocker-retry-after: environment probe succeeds",
    ):
        if snippet not in repeated_history_status_text.stdout:
            errors.append(f"version iteration history text should show repeated blocker detail: {snippet}")
    for snippet in (
        "## Latest Blocker Streak",
        "## Latest Blocker Action",
        "`repeated` streak=2 latest=`blocked-two`",
        "environment reason: `command-failed`",
        "action: `resolve-environment`",
        "retry recommended: `false`",
    ):
        if snippet not in repeated_history_status_markdown.stdout:
            errors.append(f"version iteration history Markdown should show repeated blocker detail: {snippet}")
    if "environment-blocker: cluster-unavailable (1 items)" not in history_status.stdout:
        errors.append("version iteration history text should show latest environment blocker summary")
    if "--capture-status blocked-by-environment --environment-status cluster-unavailable" not in history_status.stdout:
        errors.append("version iteration history text should show latest blocker drilldown command")
    if "environment-reason-blocker: command-failed (1 items)" not in history_status.stdout:
        errors.append("version iteration history text should show latest environment reason blocker summary")
    if "--capture-status blocked-by-environment --environment-reason command-failed" not in history_status.stdout:
        errors.append("version iteration history text should show latest environment reason drilldown command")
    if "environment-probe: unavailable" not in history_status.stdout:
        errors.append("version iteration history text should show latest environment probe status")
    if "environment-probe-reason: command-failed" not in history_status.stdout:
        errors.append("version iteration history text should show latest environment probe reason")
    if (
        "environment-probe-failure: cluster-info exit=1 reason=command-failed "
        "message=cluster unavailable from fake kubectl"
    ) not in history_status.stdout:
        errors.append("version iteration history text should show latest environment probe failure")
    if "latest-diff-status-changed: 1" not in history_status.stdout:
        errors.append("version iteration history text should show latest diff status changes")
    if "latest-diff-blocked-by-environment-delta: 1" not in history_status.stdout:
        errors.append("version iteration history text should show latest environment diff delta")
    if f"latest-artifact-run-path: {history_status_run_path}" not in history_status.stdout:
        errors.append("version iteration history text should show latest run artifact path")
    if f"latest-artifact-worklist-path: {history_status_worklist_path}" not in history_status.stdout:
        errors.append("version iteration history text should show latest worklist artifact path")
    if f"latest-artifact-diff-path: {history_status_diff_path}" not in history_status.stdout:
        errors.append("version iteration history text should show latest diff artifact path")
    if "latest-filter-versions: 0.4.3" not in history_status.stdout:
        errors.append("version iteration history text should show latest version filters")
    if "latest-filter-open-only: false" not in history_status.stdout:
        errors.append("version iteration history text should show latest open-only filter")
    if "latest-filter-probe-environment: true" not in history_status.stdout:
        errors.append("version iteration history text should show latest probe filter")
    if "latest-next-task-id: 11-resource-budget-target-idle-50m-cpu-and-64mi-memory" not in history_status.stdout:
        errors.append("version iteration history text should show latest next-task id")
    if "latest-next-task-capture-status: blocked-by-environment" not in history_status.stdout:
        errors.append("version iteration history text should show latest next-task capture status")
    if "latest-next-task-command: python3 -B scripts/capture_controller_resource_budget.py" not in history_status.stdout:
        errors.append("version iteration history text should show latest next-task command")
    if "latest-next-task-worklist: python3 -B scripts/generate_version_worklist.py" not in history_status.stdout:
        errors.append("version iteration history text should show latest next-task worklist drilldown")
    if (
        "latest-version-diff: 0.4.3 capture-ready->blocked-by-environment "
        "capture-ready-delta=-1 blocked-by-environment-delta=1 changed-items=1"
    ) not in history_status.stdout:
        errors.append("version iteration history text should show latest per-version diff")
    if f"next-command: {history_status_record_command}" not in history_status.stdout:
        errors.append("version iteration history text should show the record next command")
    if f"next-command: {history_status_iteration_command}" not in history_status.stdout:
        errors.append("version iteration history text should show the iteration next command")
    if history_status_markdown.returncode != 0:
        errors.append("version iteration history Markdown status must pass")
    if "# KubeActuary Version Iteration History Status" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown status should include a title")
    if "## Latest Artifacts" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should include latest artifact paths")
    for path in (history_status_run_path, history_status_worklist_path, history_status_diff_path):
        if path not in history_status_markdown.stdout:
            errors.append(f"version iteration history Markdown should show latest artifact path: {path}")
    if "## Latest Diff" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should include latest diff details")
    if "- status-changed: 1" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest diff status changes")
    if "- blocked-by-environment-delta: 1" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest environment diff delta")
    if "## Latest Filters" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should include latest filters")
    if "- versions: `0.4.3`" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest version filters")
    if "- probe-environment: `true`" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest probe filter")
    if "## Latest Next Task" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should include latest next-task details")
    if "`blocked-by-environment` Resource budget target: idle <50m CPU and <64Mi memory (0.4.3)" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest next-task summary")
    if "id: `11-resource-budget-target-idle-50m-cpu-and-64mi-memory`" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest next-task id")
    if "worklist: `python3 -B scripts/generate_version_worklist.py" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest next-task worklist drilldown")
    if "## Latest Version Diffs" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should include latest per-version diffs")
    if (
        "`0.4.3` capture-ready -> blocked-by-environment "
        "capture-ready-delta=-1 blocked-by-environment-delta=1 changed-items=1"
    ) not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest per-version diff")
    if "## Next Commands" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should include next commands")
    for command in (history_status_record_command, history_status_iteration_command):
        if f"- `{command}`" not in history_status_markdown.stdout:
            errors.append(f"version iteration history Markdown should show next command: {command}")
    if "environment `cluster-unavailable`: 1 items" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest environment blocker summary")
    if history_status_markdown_worklist not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest blocker drilldown command")
    if "environment reason `command-failed`: 1 items" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest environment reason blocker summary")
    if "--capture-status blocked-by-environment --environment-reason command-failed" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest environment reason drilldown command")
    if "## Latest Environment Probe" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should include environment probe details")
    if "reason: `command-failed`" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest probe reason")
    if "failed `cluster-info` exit=1 reason=command-failed: cluster unavailable from fake kubectl" not in history_status_markdown.stdout:
        errors.append("version iteration history Markdown should show latest probe failure")
    if written_history_status.returncode != 0 or not history_status_output_written:
        errors.append("version iteration history inspector must write requested output file")
    if recorded_history_status.returncode != 0:
        errors.append("version iteration history inspector must record status reports")
    if history_status_record_payload.get("record", {}).get("json") != str(history_status_record_json):
        errors.append("version iteration history recorded JSON should include record metadata")
    recorded_next_commands = history_status_record_payload.get("nextCommands", [])
    for command in (history_status_record_command, history_status_iteration_command):
        if command not in recorded_next_commands:
            errors.append(f"version iteration history recorded JSON should preserve next command: {command}")
    recorded_latest_diff = history_status_record_payload.get("latestDiffSummary", {})
    if recorded_latest_diff.get("blockedByEnvironmentDelta") != 1:
        errors.append("version iteration history recorded JSON should preserve latest diff summary")
    recorded_latest_artifacts = history_status_record_payload.get("latestArtifacts", {})
    if recorded_latest_artifacts.get("diffPath") != history_status_diff_path:
        errors.append("version iteration history recorded JSON should preserve latest artifact paths")
    recorded_latest_filters = history_status_record_payload.get("latestFilters", {})
    if recorded_latest_filters.get("versions") != ["0.4.3"]:
        errors.append("version iteration history recorded JSON should preserve latest filters")
    recorded_latest_next_task = history_status_record_payload.get("latestNextTask", {})
    if recorded_latest_next_task.get("id") != "11-resource-budget-target-idle-50m-cpu-and-64mi-memory":
        errors.append("version iteration history recorded JSON should preserve latest next-task details")
    recorded_version_diffs = history_status_record_payload.get("latestVersionDiffs", [])
    if not any(item.get("version") == "0.4.3" for item in recorded_version_diffs):
        errors.append("version iteration history recorded JSON should preserve latest per-version diffs")
    if "# KubeActuary Version Iteration History Status" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should include a title")
    if "## Latest Artifacts" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest artifact paths")
    if history_status_diff_path not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest diff artifact path")
    if "## Latest Filters" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest filters")
    if "- versions: `0.4.3`" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest version filters")
    if "## Latest Next Task" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest next-task details")
    if "id: `11-resource-budget-target-idle-50m-cpu-and-64mi-memory`" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest next-task id")
    if "## Latest Diff" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest diff details")
    if "- blocked-by-environment-delta: 1" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest diff summary")
    if "## Latest Version Diffs" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve per-version diffs")
    if "`0.4.3` capture-ready -> blocked-by-environment" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest per-version diff")
    if "## Next Commands" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve next commands")
    for command in (history_status_record_command, history_status_iteration_command):
        if f"- `{command}`" not in history_status_record_md_text:
            errors.append(f"version iteration history recorded Markdown should preserve next command: {command}")
    if "environment `cluster-unavailable`: 1 items" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest blockers")
    if "failed `cluster-info` exit=1 reason=command-failed: cluster unavailable from fake kubectl" not in history_status_record_md_text:
        errors.append("version iteration history recorded Markdown should preserve latest probe failure")
    evidence_runs = evidence_history_index.get("runs", [])
    if len(evidence_runs) != 2:
        errors.append("evidence-aware history should record two runs")
    evidence_second_run = evidence_runs[-1] if evidence_runs else {}
    if evidence_second_run.get("filters", {}).get("evidenceDir") != str(completed_evidence_dir):
        errors.append("evidence-aware history should preserve evidence directory filter")
    if evidence_second_run.get("summary", {}).get("completeEvidenceItems") != 1:
        errors.append("evidence-aware history should preserve complete evidence item count")
    if evidence_second_run.get("nextUnblockAction", {}).get("selected", {}).get("id") != "01-missing-tool-kind":
        errors.append("evidence-aware history index should preserve selected next-unblock action")
    if evidence_second_run.get("nextUnblockActionRun", {}).get("status") != "blocked":
        errors.append("evidence-aware history index should preserve next-unblock runner status")
    evidence_diff_summary = evidence_history_diff.get("summary", {})
    if evidence_diff_summary.get("completeEvidenceItemsDelta") != 1:
        errors.append("evidence-aware history diff should record complete evidence item delta")
    if evidence_diff_summary.get("existingEvidenceFilesDelta", 0) < 3:
        errors.append("evidence-aware history diff should record existing evidence file delta")
    if "evidence-files=3/" not in evidence_history_readme:
        errors.append("evidence-aware history README should summarize evidence file readiness")
    evidence_status_summary = evidence_history_status_payload.get("summary", {})
    if evidence_status_summary.get("completeEvidenceItems") != 1:
        errors.append("evidence-aware history status should summarize complete evidence items")
    if evidence_status_summary.get("existingEvidenceFiles", 0) < 3:
        errors.append("evidence-aware history status should summarize existing evidence files")
    evidence_status_filters = evidence_history_status_payload.get("latestFilters", {})
    if evidence_status_filters.get("evidenceDir") != str(completed_evidence_dir):
        errors.append("evidence-aware history status should preserve latest evidence directory filter")
    evidence_latest_advance = evidence_history_status_payload.get("latestAdvance") or {}
    if evidence_latest_advance.get("status") != "passed":
        errors.append("evidence-aware history status should include the latest advance status")
    if evidence_latest_advance.get("runnerStatus") != "passed":
        errors.append("evidence-aware history status should include the latest advance runner status")
    if evidence_latest_advance.get("runnerSummary", {}).get("ran") != 2:
        errors.append("evidence-aware history status should include latest advance runner execution counts")
    if evidence_latest_advance.get("nextTask", {}).get("selected") != "01-controller-resource-budget":
        errors.append("evidence-aware history status should include latest advance next-task summary")
    evidence_latest_advance_consistency = evidence_latest_advance.get("nextTaskConsistency") or {}
    if evidence_latest_advance_consistency.get("status") != "matched":
        errors.append("evidence-aware history status should match latest advance to latest next task")
    evidence_latest_unblock = evidence_history_status_payload.get("latestNextUnblockAction") or {}
    if evidence_latest_unblock.get("selected", {}).get("id") != "01-missing-tool-kind":
        errors.append("evidence-aware history status should preserve selected next-unblock action")
    if evidence_latest_unblock.get("selected", {}).get("target") != "kind":
        errors.append("evidence-aware history status should preserve selected next-unblock target")
    evidence_latest_unblock_run = evidence_history_status_payload.get("latestNextUnblockActionRun") or {}
    if evidence_latest_unblock_run.get("status") != "blocked":
        errors.append("evidence-aware history status should preserve next-unblock runner status")
    if (evidence_latest_unblock_run.get("failure") or {}).get("message") != "kind missing in test":
        errors.append("evidence-aware history status should preserve next-unblock runner failure")
    evidence_latest_unblock_retry = evidence_history_status_payload.get("latestNextUnblockRetry") or {}
    if evidence_latest_unblock_retry.get("recommended") is not False:
        errors.append("evidence-aware history status should suppress next-unblock retry before tool resolution")
    if evidence_latest_unblock_retry.get("retryAfter") != "required local tools are installed":
        errors.append("evidence-aware history status should explain when next-unblock retry is useful")
    stale_advance_consistency = (
        (stale_evidence_history_status_payload.get("latestAdvance") or {}).get("nextTaskConsistency") or {}
    )
    if stale_advance_consistency.get("status") != "mismatched":
        errors.append("stale advance history status should report next-task mismatch")
    if stale_advance_consistency.get("mismatches") != ["selected", "captureStatus"]:
        errors.append("stale advance history status should identify mismatched next-task fields")
    evidence_status_next_task = evidence_history_status_payload.get("latestNextTask", {})
    if evidence_status_next_task.get("version") != "Current Baseline":
        errors.append("evidence-aware history status should preserve latest next-task version")
    if not evidence_status_next_task.get("files"):
        errors.append("evidence-aware history status should preserve latest next-task files")
    if "latest-next-task-file:" not in evidence_history_status_text.stdout:
        errors.append("evidence-aware history text should show latest next-task files")
    for snippet in (
        "latest-advance-status: passed",
        "latest-advance-runner-status: passed",
        "latest-advance-runner-ran: 2/2",
        "latest-advance-next-task: 01-controller-resource-budget",
        "latest-advance-next-task-consistency: matched",
        "latest-next-unblock-action: 01-missing-tool-kind",
        "latest-next-unblock-action-target: kind",
        "latest-next-unblock-action-verify: kind version",
        "latest-next-unblock-run: blocked",
        "latest-next-unblock-run-error: kind missing in test",
        "latest-next-unblock-retry-recommended: false",
        "latest-next-unblock-retry-after: required local tools are installed",
    ):
        if snippet not in evidence_history_status_text.stdout:
            errors.append(f"evidence-aware history text should show latest advance detail: {snippet}")
    if "latest-advance-next-task-consistency: mismatched" not in stale_evidence_history_status_text.stdout:
        errors.append("stale advance history text should show latest advance mismatch")
    if "latest-advance-next-task-mismatches: selected, captureStatus" not in stale_evidence_history_status_text.stdout:
        errors.append("stale advance history text should show mismatched next-task fields")
    if "file `" not in evidence_history_status_markdown.stdout:
        errors.append("evidence-aware history Markdown should show latest next-task files")
    for snippet in (
        "## Latest Advance",
        "status: `passed`",
        "runner: `passed`",
        "runner ran: `2/2`",
        "next task: `01-controller-resource-budget`",
        "next task consistency: `matched`",
        "## Latest Next Unblock",
        "action: `01-missing-tool-kind`",
        "target: `kind`",
        "verify: `kind version`",
        "run: `blocked`",
        "run blocker: `kind missing in test`",
        "retry recommended: `false`",
        "retry after: required local tools are installed",
    ):
        if snippet not in evidence_history_status_markdown.stdout:
            errors.append(f"evidence-aware history Markdown should show latest advance detail: {snippet}")
    evidence_status_diff = evidence_history_status_payload.get("latestDiffSummary", {})
    if evidence_status_diff.get("completeEvidenceItemsDelta") != 1:
        errors.append("evidence-aware history status should preserve latest evidence diff summary")
    evidence_status_version_diffs = evidence_history_status_payload.get("latestVersionDiffs", [])
    evidence_status_version_delta = next(
        (
            item.get("summaryDelta", {})
            for item in evidence_status_version_diffs
            if item.get("version") == "Current Baseline"
        ),
        {},
    )
    if evidence_status_version_delta.get("completeEvidenceItems") != 1:
        errors.append("evidence-aware history status should preserve latest per-version evidence diff")
    if prepared_history_record.returncode != 0:
        errors.append(
            f"prepared queue history failed: "
            f"{prepared_history_record.stderr.strip() or prepared_history_record.stdout.strip()}"
        )
    if filtered_history_record.returncode != 0:
        errors.append(
            f"filtered history failed: "
            f"{filtered_history_record.stderr.strip() or filtered_history_record.stdout.strip()}"
        )
    prepared_runs = prepared_history_index.get("runs", [])
    prepared_run = prepared_runs[-1] if prepared_runs else {}
    if prepared_run.get("queueSource") != "prepared-live-validation-queue":
        errors.append("prepared queue history should preserve queue source")
    if "queue-source=prepared-live-validation-queue" not in prepared_history_readme:
        errors.append("prepared queue history README should show queue source")
    prepared_history_summary = prepared_history_status_payload.get("summary", {})
    if prepared_history_summary.get("latestQueueSource") != "prepared-live-validation-queue":
        errors.append("prepared queue history status should report latest queue source")
    filtered_history_runs = filtered_history_index.get("runs", [])
    filtered_history_run = filtered_history_runs[-1] if filtered_history_runs else {}
    if filtered_history_run.get("summary", {}).get("openItems") != 5:
        errors.append("filtered history should keep five kind-blocked items")
    if filtered_history_run.get("filters", {}).get("missingTools") != ["kind"]:
        errors.append("filtered history should preserve missing-tool filters")
    invalid_text = invalid_version_result.stdout + invalid_version_result.stderr
    if invalid_version_result.returncode == 0:
        errors.append("unknown version filter must fail")
    if "unknown version: 9.9.9" not in invalid_text:
        errors.append("unknown version filter must explain the missing version")

    summary = worklist.get("summary", {})
    versions = {version.get("version"): version for version in worklist.get("versions", []) if isinstance(version, dict)}
    if worklist.get("schemaVersion") != SCHEMA:
        errors.append("version worklist schemaVersion mismatch")
    if summary.get("openItems") != 16:
        errors.append(f"expected 16 open items, got {summary.get('openItems')!r}")
    if summary.get("captureReady") != 4:
        errors.append(f"expected 4 capture-ready items, got {summary.get('captureReady')!r}")
    if summary.get("blockedByTools") != 12:
        errors.append(f"expected 12 tool-blocked items, got {summary.get('blockedByTools')!r}")
    if summary.get("blockedByEnvironment") != 0:
        errors.append("default version worklist must not probe environment blockers")
    blockers = worklist.get("blockers", {})
    if not any(item.get("tool") == "kind" and item.get("items") == 5 for item in blockers.get("missingTools", [])):
        errors.append("default version worklist must summarize repeated kind blockers")
    kind_blocker = next(
        (item for item in blockers.get("missingTools", []) if item.get("tool") == "kind"),
        {},
    )
    if "--capture-status missing-tools --missing-tool kind" not in kind_blocker.get("worklistCommand", ""):
        errors.append("default version worklist must include missing-tool drilldown commands")
    if blockers.get("environment"):
        errors.append("default version worklist must not summarize environment blockers without a probe")
    for expected in ("Current Baseline", "0.2.0", "0.4.4", "0.9.0"):
        if expected not in versions:
            errors.append(f"version worklist missing version: {expected}")
    if versions.get("0.2.0", {}).get("status") != "complete":
        errors.append("0.2.0 worklist should be complete")
    if versions.get("Current Baseline", {}).get("status") != "capture-ready":
        errors.append("current baseline should include capture-ready work")
    if versions.get("0.4.4", {}).get("status") != "missing-tools":
        errors.append("0.4.4 should remain missing-tools until live matrix tools are available")
    version_blockers = versions.get("0.4.4", {}).get("blockers", {})
    if not any(item.get("tool") == "kind" for item in version_blockers.get("missingTools", [])):
        errors.append("0.4.4 should summarize its missing kind blocker")
    version_kind_blocker = next(
        (item for item in version_blockers.get("missingTools", []) if item.get("tool") == "kind"),
        {},
    )
    if "--version 0.4.4 --capture-status missing-tools --missing-tool kind" not in version_kind_blocker.get("worklistCommand", ""):
        errors.append("version blocker drilldown commands must preserve version filters")
    baseline_items = versions.get("Current Baseline", {}).get("openItems", [])
    if not any(item.get("captureStatus") == "tool-ready" for item in baseline_items):
        errors.append("current baseline must include a tool-ready item")
    if not any("capture_controller_resource_budget.py" in " ".join(item.get("commands", [])) for item in baseline_items):
        errors.append("current baseline must include controller resource capture command")
    if not worklist.get("closureCommands"):
        errors.append("version worklist must include closure commands")

    single_summary = single_version.get("summary", {})
    single_versions = single_version.get("versions", [])
    if single_summary.get("versions") != 1 or single_summary.get("openItems") != 1:
        errors.append("single-version filter should return one open version item")
    if single_summary.get("captureReady") != 1:
        errors.append("single-version filter should preserve capture-ready count")
    if [version.get("version") for version in single_versions] != ["0.4.3"]:
        errors.append("single-version filter should return only 0.4.3")
    if single_versions and single_versions[0].get("status") != "capture-ready":
        errors.append("0.4.3 filtered worklist should be capture-ready")

    multi_summary = multi_version.get("summary", {})
    multi_names = [version.get("version") for version in multi_version.get("versions", [])]
    if multi_names != ["0.3.3", "0.4.3"]:
        errors.append(f"multi-version filter order mismatch: {multi_names!r}")
    if multi_summary.get("versions") != 2 or multi_summary.get("captureReady") != 2:
        errors.append("multi-version filter should return two capture-ready versions")

    open_summary = open_only.get("summary", {})
    open_versions = open_only.get("versions", [])
    if open_summary.get("versions") != 9 or open_summary.get("openItems") != 16:
        errors.append("open-only filter should return nine open versions and sixteen open items")
    if any(version.get("status") == "complete" for version in open_versions):
        errors.append("open-only filter must not include complete versions")

    filtered_missing_summary = filtered_missing_status.get("summary", {})
    if filtered_missing_summary.get("openItems") != 12 or filtered_missing_summary.get("blockedByTools") != 12:
        errors.append("capture-status filter should keep the twelve missing-tool items")
    if filtered_missing_status.get("filters", {}).get("captureStatuses") != ["missing-tools"]:
        errors.append("capture-status filter should be recorded in the worklist")
    filtered_kind_summary = filtered_kind.get("summary", {})
    if filtered_kind_summary.get("openItems") != 5:
        errors.append("missing-tool filter should keep five kind-blocked items")
    filtered_kind_items = [
        item
        for version in filtered_kind.get("versions", [])
        for item in version.get("openItems", [])
        if isinstance(item, dict)
    ]
    if not filtered_kind_items or any("kind" not in item.get("missingTools", []) for item in filtered_kind_items):
        errors.append("missing-tool filter should only keep items blocked on kind")

    evidence_summary = evidence_worklist.get("summary", {})
    evidence_versions = {
        version.get("version"): version
        for version in evidence_worklist.get("versions", [])
        if isinstance(version, dict)
    }
    evidence_baseline = evidence_versions.get("Current Baseline", {})
    evidence_baseline_items = evidence_baseline.get("openItems", [])
    completed_resource_item = next(
        (item for item in evidence_baseline_items if item.get("id") == "01-controller-resource-budget"),
        {},
    )
    if evidence_worklist.get("evidenceDir") != str(completed_evidence_dir):
        errors.append("evidence-aware worklist should record the evidence directory")
    if evidence_summary.get("openItems") != 16:
        errors.append("evidence-aware worklist should preserve open item count")
    if evidence_summary.get("evidenceItems") != 16:
        errors.append("evidence-aware worklist should summarize all external evidence items")
    if evidence_summary.get("completeEvidenceItems") != 1:
        errors.append("evidence-aware worklist should count one complete evidence item")
    if evidence_summary.get("existingEvidenceFiles", 0) < 3:
        errors.append("evidence-aware worklist should count existing evidence files")
    if not evidence_worklist.get("resolvedClosureCommands"):
        errors.append("evidence-aware worklist should include resolved closure commands")
    if completed_resource_item.get("evidenceSummary", {}).get("complete") is not True:
        errors.append("evidence-aware worklist should mark the prepared resource budget task complete")
    if "resolvedCommands" not in completed_resource_item:
        errors.append("evidence-aware worklist should include resolved commands on open items")

    probe_summary = probe_worklist.get("summary", {})
    probe_versions = probe_worklist.get("versions", [])
    probe_statuses = {version.get("status") for version in probe_versions if isinstance(version, dict)}
    if probe_worklist.get("environmentProbe", {}).get("clusterAccess") != "unavailable":
        errors.append("probe worklist must report unavailable cluster access")
    if probe_worklist.get("environmentProbe", {}).get("reason") != "command-failed":
        errors.append("probe worklist must preserve unavailable-cluster reason")
    if probe_summary.get("blockedByTools") != 0:
        errors.append("fake all-tools version probe should not be blocked by missing tools")
    if probe_summary.get("blockedByEnvironment") != 14:
        errors.append(
            f"expected 14 environment-blocked worklist items, got {probe_summary.get('blockedByEnvironment')!r}"
        )
    if probe_summary.get("captureReady") != 2:
        errors.append("probe worklist should leave the two non-cluster Krew items capture-ready")
    if "blocked-by-environment" not in probe_statuses:
        errors.append("probe worklist must mark affected versions blocked-by-environment")
    probe_blockers = probe_worklist.get("blockers", {})
    probe_environment_summary = [
        {"status": item.get("status"), "items": item.get("items")}
        for item in probe_blockers.get("environment", [])
    ]
    if probe_environment_summary != [{"status": "cluster-unavailable", "items": 14}]:
        errors.append("probe worklist must summarize cluster-unavailable blockers")
    probe_environment_reason_summary = [
        {"reason": item.get("reason"), "items": item.get("items")}
        for item in probe_blockers.get("environmentReasons", [])
    ]
    if probe_environment_reason_summary != [{"reason": "command-failed", "items": 14}]:
        errors.append("probe worklist must summarize environment reason blockers")
    probe_environment_blocker = next(
        (item for item in probe_blockers.get("environment", []) if item.get("status") == "cluster-unavailable"),
        {},
    )
    if "--capture-status blocked-by-environment --environment-status cluster-unavailable" not in probe_environment_blocker.get("worklistCommand", ""):
        errors.append("probe worklist must include environment drilldown commands")
    probe_environment_reason_blocker = next(
        (item for item in probe_blockers.get("environmentReasons", []) if item.get("reason") == "command-failed"),
        {},
    )
    if "--capture-status blocked-by-environment --environment-reason command-failed" not in probe_environment_reason_blocker.get("worklistCommand", ""):
        errors.append("probe worklist must include environment-reason drilldown commands")

    prepared_summary = prepared_queue_worklist.get("summary", {})
    prepared_selected = prepared_queue_next.get("selected") or {}
    if prepared_queue_worklist.get("queueSource") != "prepared-live-validation-queue":
        errors.append("prepared evidence-dir worklist must use the persisted live validation queue")
    if prepared_queue_next.get("sourceWorklistQueueSource") != "prepared-live-validation-queue":
        errors.append("prepared evidence-dir selector must report the persisted live validation queue source")
    if prepared_queue_worklist.get("environmentProbe", {}).get("clusterAccess") != "unavailable":
        errors.append("prepared evidence-dir worklist must preserve persisted unavailable cluster access")
    if prepared_queue_worklist.get("environmentProbe", {}).get("reason") != "command-failed":
        errors.append("prepared evidence-dir worklist must preserve persisted environment reason")
    if prepared_summary.get("blockedByEnvironment") != 14:
        errors.append("prepared evidence-dir worklist must preserve persisted environment blockers")
    if prepared_summary.get("captureReady") != 2:
        errors.append("prepared evidence-dir worklist must preserve persisted capture-ready items")
    prepared_blockers = prepared_queue_worklist.get("blockers", {})
    prepared_environment_summary = [
        {"status": item.get("status"), "items": item.get("items")}
        for item in prepared_blockers.get("environment", [])
    ]
    if prepared_environment_summary != [{"status": "cluster-unavailable", "items": 14}]:
        errors.append("prepared evidence-dir worklist must preserve environment blocker summary")
    prepared_environment_reason_summary = [
        {"reason": item.get("reason"), "items": item.get("items")}
        for item in prepared_blockers.get("environmentReasons", [])
    ]
    if prepared_environment_reason_summary != [{"reason": "command-failed", "items": 14}]:
        errors.append("prepared evidence-dir worklist must preserve environment reason blocker summary")
    prepared_environment_blocker = next(
        (item for item in prepared_blockers.get("environment", []) if item.get("status") == "cluster-unavailable"),
        {},
    )
    if "--evidence-dir" not in prepared_environment_blocker.get("worklistCommand", ""):
        errors.append("prepared evidence-dir worklist blocker commands must preserve evidence-dir context")
    prepared_environment_summary = prepared_environment_filter.get("summary", {})
    if prepared_environment_summary.get("openItems") != 14 or prepared_environment_summary.get("blockedByEnvironment") != 14:
        errors.append("prepared environment-status filter should keep fourteen cluster-unavailable items")
    if prepared_environment_filter.get("filters", {}).get("environmentStatuses") != ["cluster-unavailable"]:
        errors.append("prepared environment-status filter should be recorded")
    prepared_environment_reason_summary = prepared_environment_reason_filter.get("summary", {})
    if (
        prepared_environment_reason_summary.get("openItems") != 14
        or prepared_environment_reason_summary.get("blockedByEnvironment") != 14
    ):
        errors.append("prepared environment-reason filter should keep fourteen environment-blocked items")
    if prepared_environment_reason_filter.get("filters", {}).get("environmentReasons") != ["command-failed"]:
        errors.append("prepared environment-reason filter should be recorded")
    prepared_capture_summary = prepared_capture_filter.get("summary", {})
    if prepared_capture_summary.get("openItems") != 2 or prepared_capture_summary.get("captureReady") != 2:
        errors.append("prepared capture-status filter should keep two tool-ready items")
    if prepared_selected.get("captureStatus") != "tool-ready" or prepared_selected.get("kind") != "krew":
        errors.append("prepared evidence-dir selector should use persisted queue ordering and choose a Krew item")

    next_selected = next_task.get("selected") or {}
    runnable_only_selected = next_task_runnable_only_payload.get("selected") or {}
    blocked_only_selected = next_task_blocked_only_payload.get("selected") or {}
    path_selected = next_task_with_paths.get("selected") or {}
    if next_task.get("schemaVersion") != NEXT_TASK_SCHEMA:
        errors.append("next task schemaVersion mismatch")
    if next_task.get("sourceWorklistSchema") != SCHEMA:
        errors.append("next task should record source worklist schema")
    if next_task.get("summary", {}).get("candidateItems") != 16:
        errors.append("next task should search sixteen candidate items by default")
    if next_task.get("summary", {}).get("eligibleItems") != 16:
        errors.append("next task should report sixteen eligible items by default")
    if next_selected.get("id") != "01-controller-resource-budget":
        errors.append("next task should select the first baseline tool-ready item")
    if next_selected.get("captureStatus") != "tool-ready":
        errors.append("next task default selection should be tool-ready")
    if next_selected.get("runnable") is not True:
        errors.append("next task default selection should be marked runnable")
    if next_task_runnable_only_payload.get("filters", {}).get("runnableOnly") is not True:
        errors.append("runnable-only next task should preserve runnable-only filter")
    if runnable_only_selected.get("id") != "01-controller-resource-budget":
        errors.append("runnable-only next task should keep selecting the first tool-ready item")
    if runnable_only_selected.get("runnable") is not True:
        errors.append("runnable-only next task should select runnable work")
    if next_task_runnable_only_payload.get("summary", {}).get("skippedNonRunnable") != 12:
        errors.append("runnable-only next task should report skipped non-runnable items")
    if next_task_blocked_only_payload.get("filters", {}).get("blockedOnly") is not True:
        errors.append("blocked-only next task should preserve blocked-only filter")
    if blocked_only_selected.get("id") != "02-lightweight-cluster-smoke":
        errors.append("blocked-only next task should select the first blocked item")
    if blocked_only_selected.get("captureStatus") != "missing-tools":
        errors.append("blocked-only next task should select non-runnable work")
    if blocked_only_selected.get("runnable") is not False:
        errors.append("blocked-only next task selected item should be non-runnable")
    if next_task_blocked_only_payload.get("summary", {}).get("skippedRunnable") != 4:
        errors.append("blocked-only next task should report skipped runnable items")
    for snippet in (
        "blocked-only: true",
        "skipped-runnable: 4",
        "blocked-command: python3 -B scripts/run_lightweight_cluster_smoke.py",
    ):
        if snippet not in next_task_blocked_only_text.stdout:
            errors.append(f"blocked-only next task text should show blocked selection detail: {snippet}")
    if next_task_filter_conflict.returncode == 0:
        errors.append("runnable-only and blocked-only filters should be mutually exclusive")
    if "--runnable-only and --blocked-only are mutually exclusive" not in next_task_filter_conflict.stderr:
        errors.append("conflicting selector filters should report a clear error")
    if next_task_with_paths.get("evidenceDir") != "evidence/live":
        errors.append("path-resolved next task should record the evidence directory")
    resolved_commands = "\n".join(path_selected.get("resolvedCommands", []))
    if not resolved_commands:
        errors.append("path-resolved next task should include resolved commands")
    for placeholder in ("<kubectl-top-output.txt>", "<external-evidence.json>", "<path>"):
        if placeholder in resolved_commands:
            errors.append(f"path-resolved next task must not keep placeholder: {placeholder}")
    for snippet in (
        "evidence/live/raw/01-controller-resource-budget-kubectl-top.txt",
        "evidence/live/supplemental/01-controller-resource-budget-external-2.json",
    ):
        if snippet not in resolved_commands:
            errors.append(f"path-resolved next task missing path: {snippet}")
    if "scripts/build_release_evidence_directory.py evidence/live" not in "\n".join(
        next_task_with_paths.get("resolvedClosureCommands", [])
    ):
        errors.append("path-resolved next task should include resolved closure commands")
    path_summary = path_selected.get("evidenceSummary", {})
    if path_summary.get("files") != 3 or path_summary.get("existingFiles") != 0:
        errors.append("path-resolved next task should summarize missing evidence files")
    skipped_selected = skipped_complete_payload.get("selected") or {}
    if skipped_complete_payload.get("summary", {}).get("skippedCompleteEvidence") != 1:
        errors.append("skip-complete selector should skip one completed evidence task")
    if skipped_complete_payload.get("summary", {}).get("eligibleItems") != 15:
        errors.append("skip-complete selector should leave fifteen eligible tasks")
    if skipped_selected.get("id") != "06-controller":
        errors.append("skip-complete selector should advance to the next tool-ready task")
    if skipped_selected.get("evidenceSummary", {}).get("complete") is True:
        errors.append("skip-complete selector must not select a completed evidence task")
    filtered_selected = next_task_filtered.get("selected") or {}
    if filtered_selected.get("version") != "0.4.3" or filtered_selected.get("captureStatus") != "tool-ready":
        errors.append("filtered next task should select the 0.4.3 tool-ready item")
    blocked_selected = next_task_tool_blocked.get("selected") or {}
    if blocked_selected.get("version") != "0.4.4" or blocked_selected.get("captureStatus") != "missing-tools":
        errors.append("tool-blocked next task should select the 0.4.4 missing-tools item")
    if "kind" not in blocked_selected.get("missingTools", []):
        errors.append("tool-blocked next task should preserve missing tools")
    kind_selected = next_task_kind_payload.get("selected") or {}
    if kind_selected.get("id") != "02-lightweight-cluster-smoke":
        errors.append("missing-tool filtered next task should select the first kind-blocked item")
    if next_task_kind_payload.get("summary", {}).get("candidateItems") != 5:
        errors.append("missing-tool filtered next task should search five candidate items")
    if next_task_kind_payload.get("filters", {}).get("missingTools") != ["kind"]:
        errors.append("missing-tool filtered next task should preserve missing-tool filter")
    probe_selected = probe_next_task_payload.get("selected") or {}
    if probe_next_task_payload.get("environmentProbe", {}).get("clusterAccess") != "unavailable":
        errors.append("probe next task must report unavailable cluster access")
    if probe_selected.get("captureStatus") != "tool-ready" or probe_selected.get("kind") != "krew":
        errors.append("probe next task should select a non-cluster Krew item when the cluster is unavailable")

    for path in (README, README_KO, TASKBOARD):
        text = path.read_text()
        for snippet in (
            WORKLIST_TOOL,
            PREPARE_TOOL,
            PREPARE_LIVE_TOOL,
            COMPARE_TOOL,
            RECORD_TOOL,
            INSPECT_HISTORY_TOOL,
            SELECT_TOOL,
            VERIFY_TOOL,
            SCHEMA,
            ITERATION_SCHEMA,
            DIFF_SCHEMA,
            HISTORY_SCHEMA,
            HISTORY_STATUS_SCHEMA,
            NEXT_TASK_SCHEMA,
        ):
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing version worklist detail: {snippet}")

    if errors:
        print("version-worklist: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("version-worklist: passed")
    print(f"open-items: {summary['openItems']}")
    print(f"capture-ready: {summary['captureReady']}")
    print(f"blocked-by-tools: {summary['blockedByTools']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
