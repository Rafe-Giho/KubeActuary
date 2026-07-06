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
NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"
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
        first = run_prepare(evidence_dir)
        second = run_prepare(evidence_dir)
        probe = run_prepare(probe_dir, "--probe-environment", env=fake_tool_env(Path(tmp) / "tools", cluster_ok=False))
        filtered = run_prepare(filtered_dir, "--missing-tool", "kind")
        queue_json = evidence_dir / ".kubeactuary" / "live-validation-queue.json"
        queue_md = evidence_dir / ".kubeactuary" / "live-validation-queue.md"
        next_task_json = evidence_dir / ".kubeactuary" / "next-version-task.json"
        next_task_md = evidence_dir / ".kubeactuary" / "next-version-task.md"
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
        initial_next_task_md = next_task_md.read_text() if next_task_md.is_file() else ""
        (evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt").write_text(
            "POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n"
        )
        (evidence_dir / "supplemental" / "01-controller-resource-budget-external-2.json").write_text("{}\n")
        advanced = run_prepare(evidence_dir, "--skip-complete-evidence")
        advanced_next_task = json.loads(next_task_json.read_text()) if next_task_json.is_file() else {}
        probe_queue_path = probe_dir / ".kubeactuary" / "live-validation-queue.json"
        probe_next_task_path = probe_dir / ".kubeactuary" / "next-version-task.json"
        probe_report_path = probe_dir / ".kubeactuary" / "environment-probe.json"
        probe_blockers_path = probe_dir / ".kubeactuary" / "environment-blockers.json"
        filtered_next_task_path = filtered_dir / ".kubeactuary" / "next-version-task.json"
        probe_queue = json.loads(probe_queue_path.read_text()) if probe_queue_path.is_file() else {}
        probe_next_task = json.loads(probe_next_task_path.read_text()) if probe_next_task_path.is_file() else {}
        probe_report_payload = json.loads(probe_report_path.read_text()) if probe_report_path.is_file() else {}
        probe_blockers = json.loads(probe_blockers_path.read_text()) if probe_blockers_path.is_file() else {}
        filtered_next_task = json.loads(filtered_next_task_path.read_text()) if filtered_next_task_path.is_file() else {}

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
        if advanced.returncode != 0:
            errors.append(f"advanced scaffold failed: {advanced.stderr.strip() or advanced.stdout.strip()}")
        if "skip-complete-evidence: true" not in advanced.stdout:
            errors.append("advanced scaffold must report skip-complete mode")
        if "skipped-complete-evidence: 1" not in advanced.stdout:
            errors.append("advanced scaffold must report one skipped completed task")
        for path in expected_dirs:
            if not path.is_dir():
                errors.append(f"scaffold missing directory: {path.name}")
        for path in (queue_json, queue_md, next_task_json, next_task_md, probe_json, probe_md, blockers_json, blockers_md, readme):
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
        if probe_queue.get("environmentProbe", {}).get("clusterAccess") != "unavailable":
            errors.append("probe scaffold queue must persist unavailable cluster access")
        if probe_report_payload.get("schemaVersion") != ENVIRONMENT_PROBE_SCHEMA:
            errors.append("probe scaffold environment probe schemaVersion mismatch")
        if probe_report_payload.get("clusterAccess") != "unavailable":
            errors.append("probe scaffold environment probe must record unavailable cluster access")
        if probe_report_payload.get("summary", {}).get("checks") != 2:
            errors.append("probe scaffold environment probe must record two checks")
        if probe_report_payload.get("summary", {}).get("failed") != 1:
            errors.append("probe scaffold environment probe must record one failed check")
        if probe_blockers.get("schemaVersion") != ENVIRONMENT_BLOCKERS_SCHEMA:
            errors.append("probe scaffold blocker report schemaVersion mismatch")
        if probe_blockers.get("summary", {}).get("clusterAccess") != "unavailable":
            errors.append("probe scaffold blocker report must record unavailable cluster access")
        if probe_blockers.get("summary", {}).get("blockedByEnvironment") != 14:
            errors.append("probe scaffold blocker report must count environment-blocked items")
        probe_selected = probe_next_task.get("selected") or {}
        if probe_selected.get("captureStatus") != "tool-ready" or probe_selected.get("kind") != "krew":
            errors.append("probe scaffold should select a non-cluster Krew task when cluster is unavailable")
        filtered_selected = filtered_next_task.get("selected") or {}
        if filtered_next_task.get("filters", {}).get("missingTools") != ["kind"]:
            errors.append("filtered scaffold must persist missing-tool filters")
        if filtered_selected.get("id") != "02-lightweight-cluster-smoke":
            errors.append("filtered scaffold should select the first kind-blocked task")
        if filtered_selected.get("captureStatus") != "missing-tools":
            errors.append("filtered scaffold should preserve missing-tools capture status")
        if next_task.get("schemaVersion") != NEXT_TASK_SCHEMA:
            errors.append("scaffold next task schemaVersion mismatch")
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
            NEXT_TASK_SCHEMA,
            ENVIRONMENT_PROBE_SCHEMA,
            ENVIRONMENT_BLOCKERS_SCHEMA,
            "--skip-complete-evidence",
            "--missing-tool",
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
    print("cluster-writes: disabled")
    print("environment-probe: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
