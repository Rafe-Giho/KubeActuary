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
COMPARE = ROOT / "scripts" / "compare_version_iterations.py"
RECORD = ROOT / "scripts" / "record_version_iteration.py"
INSPECT_HISTORY = ROOT / "scripts" / "inspect_version_history.py"
SELECT = ROOT / "scripts" / "select_next_version_task.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
WORKLIST_TOOL = "generate_version_worklist.py"
PREPARE_TOOL = "prepare_version_iteration.py"
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
    single_version_result = run_generator("--format", "json", "--version", "0.4.3")
    multi_version_result = run_generator("--format", "json", "--version", "0.3.3", "--version", "0.4.3")
    open_only_result = run_generator("--format", "json", "--open-only")
    invalid_version_result = run_generator("--version", "9.9.9")
    next_task_result = run_select("--format", "json")
    next_task_markdown = run_select("--format", "markdown")
    next_task_version = run_select("--format", "json", "--version", "0.4.3")
    next_task_missing = run_select("--format", "json", "--version", "0.4.4")
    next_task_paths = run_select("--format", "json", "--evidence-dir", "evidence/live")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        output = tmpdir / "worklist.json"
        written = run_generator("--output", str(output))
        output_written = output.is_file()
        probe_env = fake_all_tools_env(tmpdir / "tools", cluster_ok=False)
        probe_result = run_generator("--format", "json", "--open-only", "--probe-environment", env=probe_env)
        probe_next_task = run_select("--format", "json", "--probe-environment", env=probe_env)
        next_task_output = tmpdir / "next-task.json"
        written_next_task = run_select("--format", "json", "--output", str(next_task_output))
        next_task_output_written = next_task_output.is_file()
        completed_evidence_dir = tmpdir / "completed-evidence"
        (completed_evidence_dir / "raw").mkdir(parents=True)
        (completed_evidence_dir / "supplemental").mkdir()
        (completed_evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt").write_text(
            "POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n"
        )
        (completed_evidence_dir / "supplemental" / "01-controller-resource-budget-external-2.json").write_text("{}\n")
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
        history_status_payload = json.loads(history_status_json.stdout) if history_status_json.returncode == 0 else {}
        history_status_output = tmpdir / "history-status.json"
        written_history_status = run_inspect_history(
            str(history_dir),
            "--format",
            "json",
            "--output",
            str(history_status_output),
        )
        history_status_output_written = history_status_output.is_file()
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

    worklist = parse_worklist("json worklist", json_result, errors)
    single_version = parse_worklist("single-version worklist", single_version_result, errors)
    multi_version = parse_worklist("multi-version worklist", multi_version_result, errors)
    open_only = parse_worklist("open-only worklist", open_only_result, errors)
    probe_worklist = parse_worklist("probe worklist", probe_result, errors)
    next_task = parse_worklist("next task", next_task_result, errors)
    next_task_filtered = parse_worklist("filtered next task", next_task_version, errors)
    next_task_tool_blocked = parse_worklist("tool-blocked next task", next_task_missing, errors)
    next_task_with_paths = parse_worklist("path-resolved next task", next_task_paths, errors)
    probe_next_task_payload = parse_worklist("probe next task", probe_next_task, errors)
    evidence_worklist = parse_worklist("evidence-aware worklist", evidence_worklist_result, errors)
    skipped_complete_payload = parse_worklist("skip-complete next task", skipped_complete_task, errors)
    if markdown_result.returncode != 0:
        errors.append(f"markdown worklist failed: {markdown_result.stderr.strip() or markdown_result.stdout.strip()}")
    if "# KubeActuary Version Worklist" not in markdown_result.stdout:
        errors.append("markdown worklist missing heading")
    if written.returncode != 0 or not output_written:
        errors.append("worklist generator must write requested output file")
    if next_task_markdown.returncode != 0 or "# KubeActuary Next Version Task" not in next_task_markdown.stdout:
        errors.append("next task selector markdown must render")
    if evidence_worklist_markdown.returncode != 0 or "evidence: `3/3`" not in evidence_worklist_markdown.stdout:
        errors.append("evidence-aware worklist markdown must render file readiness")
    if written_next_task.returncode != 0 or not next_task_output_written:
        errors.append("next task selector must write requested output file")
    if skipped_complete_text.returncode != 0 or "evidence-files: 0/4" not in skipped_complete_text.stdout:
        errors.append("skip-complete next task text must report selected evidence file readiness")
    if iteration_result.returncode != 0:
        errors.append(f"version iteration pack failed: {iteration_result.stderr.strip() or iteration_result.stdout.strip()}")
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
    if "evidence: `3/3`" not in evidence_iteration_markdown:
        errors.append("evidence-aware iteration markdown must render evidence readiness")
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
    if written_history_status.returncode != 0 or not history_status_output_written:
        errors.append("version iteration history inspector must write requested output file")
    evidence_runs = evidence_history_index.get("runs", [])
    if len(evidence_runs) != 2:
        errors.append("evidence-aware history should record two runs")
    evidence_second_run = evidence_runs[-1] if evidence_runs else {}
    if evidence_second_run.get("filters", {}).get("evidenceDir") != str(completed_evidence_dir):
        errors.append("evidence-aware history should preserve evidence directory filter")
    if evidence_second_run.get("summary", {}).get("completeEvidenceItems") != 1:
        errors.append("evidence-aware history should preserve complete evidence item count")
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
    for expected in ("Current Baseline", "0.2.0", "0.4.4", "0.9.0"):
        if expected not in versions:
            errors.append(f"version worklist missing version: {expected}")
    if versions.get("0.2.0", {}).get("status") != "complete":
        errors.append("0.2.0 worklist should be complete")
    if versions.get("Current Baseline", {}).get("status") != "capture-ready":
        errors.append("current baseline should include capture-ready work")
    if versions.get("0.4.4", {}).get("status") != "missing-tools":
        errors.append("0.4.4 should remain missing-tools until live matrix tools are available")
    baseline_items = versions.get("Current Baseline", {}).get("openItems", [])
    if not any(item.get("captureStatus") == "tool-ready" for item in baseline_items):
        errors.append("current baseline must include a tool-ready item")
    if not any("measure_controller_resources.py" in " ".join(item.get("commands", [])) for item in baseline_items):
        errors.append("current baseline must include controller resource command")
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

    next_selected = next_task.get("selected") or {}
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
