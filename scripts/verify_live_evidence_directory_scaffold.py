#!/usr/bin/env python3
"""Verify live evidence directory scaffold generation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "scripts" / "prepare_live_evidence_directory.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
PREPARE_TOOL = "prepare_live_evidence_directory.py"
VERIFY_TOOL = "verify_live_evidence_directory_scaffold.py"
NEXT_TASK_TOOL = "select_next_version_task.py"
NEXT_UNBLOCK_TOOL = "select_next_unblock_action.py"
NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"
NEXT_UNBLOCK_SCHEMA = "kube-actuary.next-unblock-action.v1"
ENVIRONMENT_PROBE_SCHEMA = "kube-actuary.environment-probe.v1"
ENVIRONMENT_BLOCKERS_SCHEMA = "kube-actuary.environment-blockers.v1"


def run_prepare(path: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(PREPARE), str(path), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_tool_env(path: Path, cluster_ok: bool) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
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
    with tempfile.TemporaryDirectory() as tmp:
        evidence_dir = Path(tmp) / "evidence"
        probe_dir = Path(tmp) / "probe-evidence"
        filtered_dir = Path(tmp) / "filtered-evidence"
        version_dir = Path(tmp) / "version-evidence"
        runnable_dir = Path(tmp) / "runnable-evidence"
        blocked_dir = Path(tmp) / "blocked-evidence"
        conflict_dir = Path(tmp) / "conflict-evidence"
        first = run_prepare(evidence_dir)
        second = run_prepare(evidence_dir)
        probe = run_prepare(probe_dir, "--probe-environment", env=fake_tool_env(Path(tmp) / "tools", cluster_ok=False))
        filtered = run_prepare(filtered_dir, "--missing-tool", "kind")
        versioned = run_prepare(version_dir, "--version", "0.4.3")
        runnable_only = run_prepare(runnable_dir, "--runnable-only")
        blocked_only = run_prepare(blocked_dir, "--blocked-only")
        conflicting_modes = run_prepare(conflict_dir, "--runnable-only", "--blocked-only")
        unknown_version = run_prepare(Path(tmp) / "unknown-version", "--version", "9.9.9")
        queue_json = evidence_dir / ".kubeactuary" / "live-validation-queue.json"
        queue_md = evidence_dir / ".kubeactuary" / "live-validation-queue.md"
        next_task_json = evidence_dir / ".kubeactuary" / "next-version-task.json"
        next_task_md = evidence_dir / ".kubeactuary" / "next-version-task.md"
        next_unblock_json = evidence_dir / ".kubeactuary" / "next-unblock-action.json"
        next_unblock_md = evidence_dir / ".kubeactuary" / "next-unblock-action.md"
        probe_json = evidence_dir / ".kubeactuary" / "environment-probe.json"
        probe_md = evidence_dir / ".kubeactuary" / "environment-probe.md"
        blockers_json = evidence_dir / ".kubeactuary" / "environment-blockers.json"
        blockers_md = evidence_dir / ".kubeactuary" / "environment-blockers.md"
        readme = evidence_dir / "README.md"
        expected_dirs = [evidence_dir / name for name in ("reports", "raw", "supplemental", ".kubeactuary")]
        queue = json.loads(queue_json.read_text()) if queue_json.is_file() else {}
        next_task = json.loads(next_task_json.read_text()) if next_task_json.is_file() else {}
        probe_report = json.loads(probe_json.read_text()) if probe_json.is_file() else {}
        blockers = json.loads(blockers_json.read_text()) if blockers_json.is_file() else {}
        next_unblock = json.loads(next_unblock_json.read_text()) if next_unblock_json.is_file() else {}
        initial_next_unblock_md = next_unblock_md.read_text() if next_unblock_md.is_file() else ""
        initial_next_task_md = next_task_md.read_text() if next_task_md.is_file() else ""
        (evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt").write_text(
            "POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n"
        )
        (evidence_dir / "supplemental" / "01-controller-resource-budget-external-2.json").write_text("{}\n")
        advanced = run_prepare(evidence_dir, "--skip-complete-evidence")
        advanced_next_task = json.loads(next_task_json.read_text()) if next_task_json.is_file() else {}
        probe_queue_path = probe_dir / ".kubeactuary" / "live-validation-queue.json"
        probe_next_task_path = probe_dir / ".kubeactuary" / "next-version-task.json"
        probe_next_unblock_path = probe_dir / ".kubeactuary" / "next-unblock-action.json"
        probe_report_path = probe_dir / ".kubeactuary" / "environment-probe.json"
        probe_blockers_path = probe_dir / ".kubeactuary" / "environment-blockers.json"
        filtered_next_task_path = filtered_dir / ".kubeactuary" / "next-version-task.json"
        filtered_next_unblock_path = filtered_dir / ".kubeactuary" / "next-unblock-action.json"
        version_next_task_path = version_dir / ".kubeactuary" / "next-version-task.json"
        version_next_unblock_path = version_dir / ".kubeactuary" / "next-unblock-action.json"
        version_next_task_md_path = version_dir / ".kubeactuary" / "next-version-task.md"
        runnable_next_task_path = runnable_dir / ".kubeactuary" / "next-version-task.json"
        blocked_next_task_path = blocked_dir / ".kubeactuary" / "next-version-task.json"
        probe_queue = json.loads(probe_queue_path.read_text()) if probe_queue_path.is_file() else {}
        probe_next_task = json.loads(probe_next_task_path.read_text()) if probe_next_task_path.is_file() else {}
        probe_next_unblock = json.loads(probe_next_unblock_path.read_text()) if probe_next_unblock_path.is_file() else {}
        probe_report_payload = json.loads(probe_report_path.read_text()) if probe_report_path.is_file() else {}
        probe_blockers = json.loads(probe_blockers_path.read_text()) if probe_blockers_path.is_file() else {}
        filtered_next_task = json.loads(filtered_next_task_path.read_text()) if filtered_next_task_path.is_file() else {}
        filtered_next_unblock = json.loads(filtered_next_unblock_path.read_text()) if filtered_next_unblock_path.is_file() else {}
        version_next_task = json.loads(version_next_task_path.read_text()) if version_next_task_path.is_file() else {}
        version_next_unblock = json.loads(version_next_unblock_path.read_text()) if version_next_unblock_path.is_file() else {}
        version_next_task_md = version_next_task_md_path.read_text() if version_next_task_md_path.is_file() else ""
        runnable_next_task = json.loads(runnable_next_task_path.read_text()) if runnable_next_task_path.is_file() else {}
        blocked_next_task = json.loads(blocked_next_task_path.read_text()) if blocked_next_task_path.is_file() else {}

        for name, result in (("first", first), ("second", second)):
            if result.returncode != 0:
                errors.append(f"{name} scaffold failed: {result.stderr.strip() or result.stdout.strip()}")
        if "live-evidence-directory: prepared" not in second.stdout:
            errors.append("scaffold must report prepared status")
        if "cluster-writes: disabled" not in second.stdout:
            errors.append("scaffold must report disabled writes")
        if probe.returncode != 0:
            errors.append(f"probe scaffold failed: {probe.stderr.strip() or probe.stdout.strip()}")
        if "probe-environment: true" not in probe.stdout or "cluster-access: unavailable" not in probe.stdout:
            errors.append("probe scaffold must report unavailable cluster access")
        if filtered.returncode != 0:
            errors.append(f"filtered scaffold failed: {filtered.stderr.strip() or filtered.stdout.strip()}")
        if versioned.returncode != 0:
            errors.append(f"versioned scaffold failed: {versioned.stderr.strip() or versioned.stdout.strip()}")
        if "version: 0.4.3" not in versioned.stdout:
            errors.append("versioned scaffold must print selected version filters")
        if runnable_only.returncode != 0:
            errors.append(f"runnable-only scaffold failed: {runnable_only.stderr.strip() or runnable_only.stdout.strip()}")
        if "runnable-only: true" not in runnable_only.stdout:
            errors.append("runnable-only scaffold must print runnable-only mode")
        if blocked_only.returncode != 0:
            errors.append(f"blocked-only scaffold failed: {blocked_only.stderr.strip() or blocked_only.stdout.strip()}")
        if "blocked-only: true" not in blocked_only.stdout:
            errors.append("blocked-only scaffold must print blocked-only mode")
        if conflicting_modes.returncode == 0:
            errors.append("conflicting scaffold selector modes must fail")
        if "--runnable-only and --blocked-only are mutually exclusive" not in conflicting_modes.stdout:
            errors.append("conflicting scaffold selector modes should report the selector conflict")
        if unknown_version.returncode == 0 or "unknown version: 9.9.9" not in unknown_version.stdout:
            errors.append("versioned scaffold must reject unknown version filters")
        if advanced.returncode != 0:
            errors.append(f"advanced scaffold failed: {advanced.stderr.strip() or advanced.stdout.strip()}")
        if "skip-complete-evidence: true" not in advanced.stdout:
            errors.append("advanced scaffold must report skip-complete mode")
        if "skipped-complete-evidence: 1" not in advanced.stdout:
            errors.append("advanced scaffold must report one skipped completed task")
        for path in expected_dirs:
            if not path.is_dir():
                errors.append(f"scaffold missing directory: {path.name}")
        for path in (
            queue_json,
            queue_md,
            next_task_json,
            next_task_md,
            next_unblock_json,
            next_unblock_md,
            probe_json,
            probe_md,
            blockers_json,
            blockers_md,
            readme,
        ):
            if not path.is_file():
                errors.append(f"scaffold missing file: {path.name}")
        if queue.get("schemaVersion") != "kube-actuary.live-validation-queue.v1":
            errors.append("scaffold queue schemaVersion mismatch")
        if probe_report.get("schemaVersion") != ENVIRONMENT_PROBE_SCHEMA:
            errors.append("scaffold environment probe schemaVersion mismatch")
        if probe_report.get("clusterAccess") != "not-run":
            errors.append("default scaffold environment probe should mark probe not-run")
        if probe_report.get("summary", {}).get("checks") != 0:
            errors.append("default scaffold environment probe should have zero checks")
        if blockers.get("schemaVersion") != ENVIRONMENT_BLOCKERS_SCHEMA:
            errors.append("scaffold blocker report schemaVersion mismatch")
        if blockers.get("summary", {}).get("clusterAccess") != "not-run":
            errors.append("default scaffold blocker report should mark probe not-run")
        if queue.get("summary", {}).get("total") != 16:
            errors.append("scaffold queue must include 16 items")
        if queue.get("evidenceDir") != str(evidence_dir):
            errors.append("scaffold queue must record evidence directory")
        resolved = "\n".join(
            command
            for item in queue.get("items", [])
            for command in item.get("resolvedCommands", [])
        )
        if str(evidence_dir / "reports") not in resolved:
            errors.append("scaffold queue must resolve report paths under reports/")
        if str(evidence_dir / "supplemental") not in resolved:
            errors.append("scaffold queue must resolve supplemental paths")
        if "cluster-writes: `disabled`" not in readme.read_text():
            errors.append("scaffold README must document disabled writes")
        if "next-version-task" not in readme.read_text():
            errors.append("scaffold README must point to next-task artifacts")
        if "next-unblock-action" not in readme.read_text():
            errors.append("scaffold README must point to next-unblock artifacts")
        if probe_queue.get("environmentProbe", {}).get("clusterAccess") != "unavailable":
            errors.append("probe scaffold queue must persist unavailable cluster access")
        if probe_report_payload.get("schemaVersion") != ENVIRONMENT_PROBE_SCHEMA:
            errors.append("probe scaffold environment probe schemaVersion mismatch")
        if probe_report_payload.get("clusterAccess") != "unavailable":
            errors.append("probe scaffold environment probe must record unavailable cluster access")
        if probe_report_payload.get("reason") != "connection-refused":
            errors.append("probe scaffold environment probe must record unavailable-cluster reason")
        if probe_report_payload.get("summary", {}).get("checks") != 2:
            errors.append("probe scaffold environment probe must record two checks")
        if probe_report_payload.get("summary", {}).get("failed") != 1:
            errors.append("probe scaffold environment probe must record one failed check")
        probe_cluster_check = next(
            (
                item
                for item in probe_report_payload.get("checks", [])
                if isinstance(item, dict) and item.get("name") == "cluster-info"
            ),
            {},
        )
        if probe_cluster_check.get("reason") != "connection-refused":
            errors.append("probe scaffold environment probe must preserve failed check reason")
        if probe_blockers.get("schemaVersion") != ENVIRONMENT_BLOCKERS_SCHEMA:
            errors.append("probe scaffold blocker report schemaVersion mismatch")
        if probe_blockers.get("summary", {}).get("clusterAccess") != "unavailable":
            errors.append("probe scaffold blocker report must record unavailable cluster access")
        if probe_blockers.get("summary", {}).get("reason") != "connection-refused":
            errors.append("probe scaffold blocker report must record unavailable-cluster reason")
        if probe_blockers.get("summary", {}).get("blockedByEnvironment") != 14:
            errors.append("probe scaffold blocker report must count environment-blocked items")
        if not any(
            item.get("environmentReason") == "connection-refused"
            for item in probe_queue.get("items", [])
            if isinstance(item, dict)
        ):
            errors.append("probe scaffold queue must preserve item environment reason")
        if not any(
            item.get("environmentReason") == "connection-refused"
            for item in probe_blockers.get("items", [])
            if isinstance(item, dict)
        ):
            errors.append("probe scaffold blocker report must preserve item environment reason")
        probe_selected = probe_next_task.get("selected") or {}
        if probe_selected.get("captureStatus") != "tool-ready" or probe_selected.get("kind") != "krew":
            errors.append("probe scaffold should select a non-cluster Krew task when cluster is unavailable")
        if probe_next_task.get("sourceWorklistQueueSource") != "prepared-live-validation-queue":
            errors.append("probe scaffold next task must use the prepared live validation queue")
        if probe_next_task.get("filters", {}).get("probeEnvironment") is not True:
            errors.append("probe scaffold next task must preserve probe-environment filters")
        probe_unblock_selected = probe_next_unblock.get("selected") or {}
        if probe_next_unblock.get("schemaVersion") != NEXT_UNBLOCK_SCHEMA:
            errors.append("probe scaffold next-unblock schemaVersion mismatch")
        if probe_next_unblock.get("filters", {}).get("probeEnvironment") is not True:
            errors.append("probe scaffold next-unblock must preserve probe-environment filters")
        if probe_unblock_selected.get("kind") != "environment":
            errors.append("probe scaffold next-unblock should select the shared environment blocker")
        if probe_unblock_selected.get("environmentReason") != "connection-refused":
            errors.append("probe scaffold next-unblock must preserve environment reason")
        filtered_selected = filtered_next_task.get("selected") or {}
        if filtered_next_task.get("filters", {}).get("missingTools") != ["kind"]:
            errors.append("filtered scaffold must persist missing-tool filters")
        if filtered_selected.get("id") != "02-lightweight-cluster-smoke":
            errors.append("filtered scaffold should select the first kind-blocked task")
        if filtered_selected.get("captureStatus") != "missing-tools":
            errors.append("filtered scaffold should preserve missing-tools capture status")
        filtered_unblock_selected = filtered_next_unblock.get("selected") or {}
        if filtered_next_unblock.get("filters", {}).get("missingTools") != ["kind"]:
            errors.append("filtered scaffold next-unblock must persist missing-tool filters")
        if filtered_unblock_selected.get("tool") != "kind":
            errors.append("filtered scaffold next-unblock should select the kind unblock action")
        version_selected = version_next_task.get("selected") or {}
        if version_next_task.get("filters", {}).get("versions") != ["0.4.3"]:
            errors.append("versioned scaffold must persist version filters")
        if version_selected.get("id") != "11-resource-budget-target-idle-50m-cpu-and-64mi-memory":
            errors.append("versioned scaffold should select the first open task in v0.4.3")
        if version_selected.get("version") != "0.4.3":
            errors.append("versioned scaffold must preserve selected task version")
        if "0.4.3" not in version_next_task_md:
            errors.append("versioned scaffold next-task markdown must show the selected version")
        if version_next_unblock.get("filters", {}).get("versions") != ["0.4.3"]:
            errors.append("versioned scaffold next-unblock must persist version filters")
        runnable_selected = runnable_next_task.get("selected") or {}
        if runnable_next_task.get("filters", {}).get("runnableOnly") is not True:
            errors.append("runnable-only scaffold must persist runnable-only filter")
        if runnable_selected.get("id") != "01-controller-resource-budget":
            errors.append("runnable-only scaffold should select the first runnable task")
        if runnable_selected.get("runnable") is not True:
            errors.append("runnable-only scaffold selected task should be runnable")
        blocked_selected = blocked_next_task.get("selected") or {}
        if blocked_next_task.get("filters", {}).get("blockedOnly") is not True:
            errors.append("blocked-only scaffold must persist blocked-only filter")
        if blocked_selected.get("id") != "02-lightweight-cluster-smoke":
            errors.append("blocked-only scaffold should select the first blocked task")
        if blocked_selected.get("runnable") is not False:
            errors.append("blocked-only scaffold selected task should be non-runnable")
        if next_task.get("schemaVersion") != NEXT_TASK_SCHEMA:
            errors.append("scaffold next task schemaVersion mismatch")
        if next_unblock.get("schemaVersion") != NEXT_UNBLOCK_SCHEMA:
            errors.append("scaffold next-unblock schemaVersion mismatch")
        if next_unblock.get("evidenceDir") != str(evidence_dir):
            errors.append("scaffold next-unblock must record evidence directory")
        if next_unblock.get("sourceWorklistQueueSource") != "prepared-live-validation-queue":
            errors.append("scaffold next-unblock must use the prepared live validation queue")
        next_unblock_selected = next_unblock.get("selected") or {}
        if next_unblock_selected.get("kind") != "missing-tool":
            errors.append("scaffold next-unblock should select a missing-tool blocker by default")
        if not next_unblock_selected.get("commands", {}).get("verify"):
            errors.append("scaffold next-unblock must include verification commands")
        if next_task.get("evidenceDir") != str(evidence_dir):
            errors.append("scaffold next task must record evidence directory")
        if next_task.get("sourceWorklistQueueSource") != "prepared-live-validation-queue":
            errors.append("scaffold next task must use the prepared live validation queue")
        selected = next_task.get("selected") or {}
        resolved_next = "\n".join(selected.get("resolvedCommands", []))
        if selected.get("id") != "01-controller-resource-budget":
            errors.append("scaffold next task should select the first tool-ready task")
        if str(evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt") not in resolved_next:
            errors.append("scaffold next task must resolve raw evidence path")
        if str(evidence_dir / "supplemental" / "01-controller-resource-budget-external-2.json") not in resolved_next:
            errors.append("scaffold next task must resolve supplemental evidence path")
        if "<kubectl-top-output.txt>" in resolved_next or "<external-evidence.json>" in resolved_next:
            errors.append("scaffold next task must not keep placeholders in resolved commands")
        if "Controller resource budget" not in initial_next_task_md:
            errors.append("scaffold next task markdown must summarize selected task")
        if "Queue source: `prepared-live-validation-queue`" not in initial_next_task_md:
            errors.append("scaffold next task markdown must show prepared queue source")
        if "# KubeActuary Next Unblock Action" not in initial_next_unblock_md:
            errors.append("scaffold next-unblock markdown must render title")
        if "Selection policy: `highest-items-then-kind-target`" not in initial_next_unblock_md:
            errors.append("scaffold next-unblock markdown must show selection policy")
        advanced_selected = advanced_next_task.get("selected") or {}
        advanced_summary = advanced_next_task.get("summary", {})
        if advanced_summary.get("skippedCompleteEvidence") != 1:
            errors.append("advanced scaffold should skip one completed evidence task")
        if advanced_selected.get("id") != "06-controller":
            errors.append("advanced scaffold should select the next incomplete tool-ready task")
        if advanced_selected.get("evidenceSummary", {}).get("complete") is True:
            errors.append("advanced scaffold must not select a completed evidence task")

    for path in (README, README_KO, TASKBOARD, LIVE_VALIDATION):
        text = path.read_text()
        for snippet in (
            PREPARE_TOOL,
            VERIFY_TOOL,
            NEXT_TASK_TOOL,
            NEXT_UNBLOCK_TOOL,
            NEXT_TASK_SCHEMA,
            NEXT_UNBLOCK_SCHEMA,
            ENVIRONMENT_PROBE_SCHEMA,
            ENVIRONMENT_BLOCKERS_SCHEMA,
            "--skip-complete-evidence",
            "--missing-tool",
            "--version",
            "--runnable-only",
            "--blocked-only",
        ):
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing scaffold detail: {snippet}")

    if errors:
        print("live-evidence-directory-scaffold: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("live-evidence-directory-scaffold: passed")
    print("directories: 4")
    print("queue-items: 16")
    print("next-task: selected")
    print("next-unblock-action: selected")
    print("cluster-writes: disabled")
    print("environment-probe: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
