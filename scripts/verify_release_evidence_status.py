#!/usr/bin/env python3
"""Verify release evidence directory status inspection."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "scripts" / "inspect_release_evidence_directory.py"
EVIDENCE_BUILDER = ROOT / "scripts" / "build_external_evidence.py"
NEXT_TASK_BUILDER = ROOT / "scripts" / "build_next_task_evidence.py"
PREPARE = ROOT / "scripts" / "prepare_live_evidence_directory.py"
README = ROOT / "README.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"
sys.path.insert(0, str(ROOT))

from scripts.inspect_release_evidence_directory import render_markdown, render_text  # noqa: E402
from scripts.verify_live_evidence_schema import sample  # noqa: E402


NEXT_TASK_SCHEMA = "kube-actuary.next-version-task.v1"
NEXT_TASK_BUILD_SCHEMA = "kube-actuary.next-task-evidence-build.v1"
NEXT_TASK_RUN_SCHEMA = "kube-actuary.next-version-task-run.v1"
ENVIRONMENT_PROBE_SCHEMA = "kube-actuary.environment-probe.v1"
ENVIRONMENT_BLOCKERS_SCHEMA = "kube-actuary.environment-blockers.v1"
ADVANCE_SCHEMA = "kube-actuary.version-iteration-advance.v1"
LIGHTWEIGHT_PROVIDERS = ("kind", "minikube", "microk8s", "k3s")
MANAGED_PROVIDERS = ("eks", "gke", "aks")
SINGLE_REPORT_SCHEMAS = (
    "kube-actuary.helm-smoke.v1",
    "kube-actuary.krew-smoke.v1",
    "kube-actuary.admission-kind-smoke.v1",
)


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(script), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_script_with_env(script: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(script), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_probe_env(path: Path) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    kubectl = path / "kubectl"
    kubectl.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['version']:\n"
        "    print('Client Version: fake')\n"
        "    raise SystemExit(0)\n"
        "if args[:1] == ['cluster-info']:\n"
        "    print('cluster unavailable', file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "raise SystemExit(0)\n"
    )
    kubectl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', '')}"
    return env


def write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload))


def write_next_task_run(evidence_dir: Path) -> None:
    write_payload(
        evidence_dir / ".kubeactuary" / "next-version-task-run.json",
        {
            "schemaVersion": NEXT_TASK_RUN_SCHEMA,
            "mode": "run",
            "status": "failed",
            "clusterWrites": "disabled-or-server-side-dry-run-only",
            "ranAt": "2026-07-06T00:00:00+00:00",
            "nextTask": {
                "schemaVersion": NEXT_TASK_SCHEMA,
                "selected": {
                    "id": "01-controller-resource-budget",
                    "version": "Current Baseline",
                    "item": "Controller resource budget",
                    "kind": "controller-resource-budget",
                    "captureStatus": "tool-ready",
                },
            },
            "summary": {
                "commands": 2,
                "validCommands": 2,
                "ran": 2,
                "failed": 1,
                "validationErrors": 0,
            },
            "records": [
                {
                    "command": "python3 -B scripts/capture_controller_resource_budget.py --output raw.txt --run",
                    "exitCode": 1,
                    "ok": False,
                    "stderr": "",
                    "stdout": "controller-resource-capture: failed\nerror: test cluster unavailable\n",
                }
            ],
        },
    )


def write_advance_record(evidence_dir: Path) -> None:
    write_payload(
        evidence_dir / ".kubeactuary" / "version-iteration-advance.json",
        {
            "schemaVersion": ADVANCE_SCHEMA,
            "mode": "run",
            "status": "passed",
            "clusterWrites": "disabled-or-server-side-dry-run-only",
            "runId": "test-advance",
            "createdAt": "2026-07-06T00:00:00+00:00",
            "runner": {"status": "passed"},
            "nextTask": {
                "selected": "06-controller",
                "skippedCompleteEvidence": 1,
            },
            "history": {"runs": 2},
        },
    )


def write_full_matrix(evidence_dir: Path) -> None:
    for provider in LIGHTWEIGHT_PROVIDERS:
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = provider
        write_payload(evidence_dir / f"lightweight-{provider}.json", payload)
    for provider in MANAGED_PROVIDERS:
        payload = sample("kube-actuary.managed-kubernetes-smoke.v1")
        payload["provider"] = provider
        write_payload(evidence_dir / f"managed-{provider}.json", payload)
    for index, schema in enumerate(SINGLE_REPORT_SCHEMAS):
        write_payload(evidence_dir / f"single-{index}.json", sample(schema))


def build_supplemental(evidence_dir: Path, kind: str, source: Path) -> None:
    output = evidence_dir / f"{kind}.json"
    result = run_script(EVIDENCE_BUILDER, "--kind", kind, "--source", str(source), "--output", str(output))
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip())


def write_supplemental(evidence_dir: Path, tmpdir: Path) -> None:
    explain = tmpdir / "explain.txt"
    explain.write_text("KIND: OperationCapsule\nFIELDS:\n  spec\n  status\n")
    budget = tmpdir / "kubectl-top.txt"
    budget.write_text("POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n")
    loop = tmpdir / "loop.json"
    loop.write_text(json.dumps({"mode": "server-dry-run-loop", "writeExecution": "disabled", "readExecution": "kubectl-get", "failed": 0}))
    build_supplemental(evidence_dir, "kubectl-explain", explain)
    build_supplemental(evidence_dir, "controller-resource-budget", budget)
    build_supplemental(evidence_dir, "controller-live-loop", loop)


def main() -> int:
    errors: list[str] = []
    synthetic_status = {
        "schemaVersion": "kube-actuary.release-evidence-status.v1",
        "evidenceDir": "synthetic-evidence",
        "summary": {
            "status": "partial",
            "liveReports": 0,
            "supplementalEvidence": 0,
            "coveredGates": 0,
            "totalGates": 16,
            "coverageErrors": 0,
        },
        "nextCommands": [f"python3 -B scripts/synthetic_next_{index}.py" for index in range(1, 7)],
        "nextTask": {
            "selected": {
                "id": "synthetic-next-task",
                "item": "Synthetic next task",
                "captureStatus": "tool-ready",
                "files": [
                    {
                        "role": "output",
                        "path": f"evidence/live/raw/synthetic-{index}.txt",
                        "exists": False,
                    }
                    for index in range(1, 6)
                ],
                "resolvedCommands": [
                    f"python3 -B scripts/synthetic_command_{index}.py"
                    for index in range(1, 4)
                ],
            },
            "summary": {"files": 5, "existingFiles": 0, "missingFiles": 5},
        },
    }
    synthetic_text = render_text(synthetic_status)
    synthetic_markdown = render_markdown(synthetic_status)
    for snippet in (
        "next: python3 -B scripts/synthetic_next_6.py",
        "next-task-file: missing output evidence/live/raw/synthetic-5.txt",
        "next-task-command: python3 -B scripts/synthetic_command_3.py",
    ):
        if snippet not in synthetic_text:
            errors.append(f"text evidence status must include all local task details: {snippet}")
    if "python3 -B scripts/synthetic_next_6.py" not in synthetic_markdown:
        errors.append("markdown evidence status must include all next commands")
    for snippet in (
        "file: `missing` `output` `evidence/live/raw/synthetic-5.txt`",
        "command: `python3 -B scripts/synthetic_command_3.py`",
    ):
        if snippet not in synthetic_markdown:
            errors.append(f"markdown evidence status must include all selected next-task details: {snippet}")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        partial_dir = tmpdir / "partial"
        prepared = run_script(PREPARE, str(partial_dir))
        if prepared.returncode != 0:
            errors.append(f"partial scaffold failed: {prepared.stderr.strip() or prepared.stdout.strip()}")
        payload = sample("kube-actuary.lightweight-smoke.v1")
        payload["provider"] = "kind"
        write_payload(partial_dir / "reports" / "kind.json", payload)
        (partial_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt").write_text(
            "POD NAME CPU(cores) MEMORY(bytes)\ncontroller-0 controller 12m 41Mi\n"
        )
        write_next_task_run(partial_dir)
        write_advance_record(partial_dir)
        partial = run_script(INSPECTOR, str(partial_dir), "--format", "json")
        partial_text = run_script(INSPECTOR, str(partial_dir))
        partial_markdown = run_script(INSPECTOR, str(partial_dir), "--format", "markdown")
        recorded = run_script(INSPECTOR, str(partial_dir), "--format", "json", "--record")
        recorded_json = partial_dir / ".kubeactuary" / "release-evidence-status.json"
        recorded_md = partial_dir / ".kubeactuary" / "release-evidence-status.md"
        recorded_output_written = recorded_json.is_file() and recorded_md.is_file()
        recorded_file_payload = json.loads(recorded_json.read_text()) if recorded_json.is_file() else {}
        recorded_markdown = recorded_md.read_text() if recorded_md.is_file() else ""
        next_task_build = run_script(NEXT_TASK_BUILDER, str(partial_dir), "--format", "json")
        next_task_output = partial_dir / "supplemental" / "01-controller-resource-budget-external-2.json"
        next_task_output_written = next_task_output.is_file()
        next_task_build_again = run_script(NEXT_TASK_BUILDER, str(partial_dir))
        partial_after_build = run_script(INSPECTOR, str(partial_dir), "--format", "json")
        partial_after_build_text = run_script(INSPECTOR, str(partial_dir))

        blocked_dir = tmpdir / "blocked"
        blocked_prepared = run_script_with_env(
            PREPARE,
            str(blocked_dir),
            "--probe-environment",
            env=fake_probe_env(tmpdir / "probe-tools"),
        )
        blocked = run_script(INSPECTOR, str(blocked_dir), "--format", "json")
        blocked_text = run_script(INSPECTOR, str(blocked_dir))

        stale_dir = tmpdir / "stale"
        stale_prepared = run_script(PREPARE, str(stale_dir))
        stale_next_task_path = stale_dir / ".kubeactuary" / "next-version-task.json"
        if stale_next_task_path.is_file():
            stale_next_task_payload = json.loads(stale_next_task_path.read_text())
            stale_next_task_payload.setdefault("selected", {})["captureStatus"] = "missing-tools"
            write_payload(stale_next_task_path, stale_next_task_payload)
        stale = run_script(INSPECTOR, str(stale_dir), "--format", "json")
        stale_text = run_script(INSPECTOR, str(stale_dir))

        full_dir = tmpdir / "full"
        full_dir.mkdir()
        write_full_matrix(full_dir)
        try:
            write_supplemental(full_dir, tmpdir)
        except RuntimeError as exc:
            errors.append(f"supplemental evidence build failed: {exc}")
        complete = run_script(INSPECTOR, str(full_dir), "--format", "json")
        text = run_script(INSPECTOR, str(full_dir))

        output = tmpdir / "status.json"
        written = run_script(INSPECTOR, str(full_dir), "--format", "json", "--output", str(output))
        output_written = output.is_file()

        invalid_dir = tmpdir / "invalid"
        invalid_dir.mkdir()
        write_payload(invalid_dir / "bad.json", {"schemaVersion": "kube-actuary.external-evidence.v1", "kind": "kubectl-explain", "ok": False})
        invalid = run_script(INSPECTOR, str(invalid_dir))
        unprepared_next_task_build = run_script(NEXT_TASK_BUILDER, str(tmpdir / "unprepared"))

    if partial.returncode != 0:
        errors.append(f"partial status failed: {partial.stderr.strip() or partial.stdout.strip()}")
        partial_payload = {}
    else:
        partial_payload = json.loads(partial.stdout)
    if recorded.returncode != 0:
        errors.append(f"recorded status failed: {recorded.stderr.strip() or recorded.stdout.strip()}")
        recorded_payload = {}
    else:
        recorded_payload = json.loads(recorded.stdout)
    if next_task_build.returncode != 0:
        errors.append(f"next-task evidence build failed: {next_task_build.stderr.strip() or next_task_build.stdout.strip()}")
        next_task_build_payload = {}
    else:
        next_task_build_payload = json.loads(next_task_build.stdout)
    if partial_after_build.returncode != 0:
        errors.append(f"post-build partial status failed: {partial_after_build.stderr.strip() or partial_after_build.stdout.strip()}")
        partial_after_build_payload = {}
    else:
        partial_after_build_payload = json.loads(partial_after_build.stdout)
    if blocked_prepared.returncode != 0:
        errors.append(f"blocked evidence prepare failed: {blocked_prepared.stderr.strip() or blocked_prepared.stdout.strip()}")
    if blocked.returncode != 0:
        errors.append(f"blocked evidence status failed: {blocked.stderr.strip() or blocked.stdout.strip()}")
        blocked_payload = {}
    else:
        blocked_payload = json.loads(blocked.stdout)
    if stale_prepared.returncode != 0:
        errors.append(f"stale evidence prepare failed: {stale_prepared.stderr.strip() or stale_prepared.stdout.strip()}")
    if stale.returncode != 0:
        errors.append(f"stale evidence status failed: {stale.stderr.strip() or stale.stdout.strip()}")
        stale_payload = {}
    else:
        stale_payload = json.loads(stale.stdout)
    if complete.returncode != 0:
        errors.append(f"complete status failed: {complete.stderr.strip() or complete.stdout.strip()}")
        complete_payload = {}
    else:
        complete_payload = json.loads(complete.stdout)
    if text.returncode != 0 or "release-evidence-status: complete" not in text.stdout:
        errors.append("text status output must report complete status")
    if written.returncode != 0 or not output_written:
        errors.append("status inspector must write requested output file")
    if invalid.returncode == 0 or "supplemental evidence must be ok=true" not in invalid.stdout:
        errors.append("status inspector must reject invalid supplemental evidence")
    if unprepared_next_task_build.returncode == 0:
        errors.append("next-task evidence build must fail for an unprepared evidence directory")
    if "prepare_live_evidence_directory.py" not in unprepared_next_task_build.stdout:
        errors.append("next-task evidence build unprepared error must include the prepare command")

    if partial_payload.get("schemaVersion") != "kube-actuary.release-evidence-status.v1":
        errors.append("status schemaVersion mismatch")
    if partial_markdown.returncode != 0:
        errors.append(f"partial Markdown status failed: {partial_markdown.stderr.strip() or partial_markdown.stdout.strip()}")
    for snippet in (
        "# KubeActuary Release Evidence Status",
        "file: `present` `output`",
        "command: `python3 -B scripts/capture_controller_resource_budget.py",
        "history runs: 2",
    ):
        if snippet not in partial_markdown.stdout:
            errors.append(f"partial Markdown status should include detail: {snippet}")
    if recorded_payload.get("schemaVersion") != "kube-actuary.release-evidence-status.v1":
        errors.append("recorded status stdout schemaVersion mismatch")
    if "release-evidence-status: recorded" in recorded.stdout:
        errors.append("recorded status notice must not corrupt JSON stdout")
    if not recorded_output_written:
        errors.append("status inspector --record must write JSON and Markdown reports")
    if "# KubeActuary Release Evidence Status" not in recorded_markdown:
        errors.append("recorded status Markdown must include the report title")
    if recorded_file_payload.get("schemaVersion") != "kube-actuary.release-evidence-status.v1":
        errors.append("recorded status file schemaVersion mismatch")
    if recorded_file_payload.get("summary", {}).get("status") != "partial":
        errors.append("recorded status file must preserve partial status")
    if "prepared-live-validation-queue" not in recorded_markdown:
        errors.append("recorded status Markdown must preserve queue source")
    if partial_payload.get("summary", {}).get("status") != "partial":
        errors.append("partial evidence directory must report partial")
    if partial_payload.get("summary", {}).get("liveReports") != 1:
        errors.append("partial evidence directory must count one live report")
    if not partial_payload.get("missing", {}).get("coverage"):
        errors.append("partial status must include coverage misses")
    if any("run_managed_kubernetes_smoke.py" in command for command in partial_payload.get("nextCommands", [])):
        errors.append("partial status must not recommend missing-tool provider commands")
    expected_probe_command = f"python3 -B scripts/prepare_live_evidence_directory.py {partial_dir} --probe-environment"
    if not partial_payload.get("nextCommands") or partial_payload.get("nextCommands", [None])[0] != expected_probe_command:
        errors.append("partial status must recommend environment probing before more live capture after runner failure")
    expected_resolved_capture = (
        f"python3 -B scripts/capture_controller_resource_budget.py "
        f"--output {partial_dir / 'raw' / '01-controller-resource-budget-kubectl-top.txt'} --run"
    )
    if len(partial_payload.get("nextCommands", [])) < 2 or partial_payload["nextCommands"][1] != expected_resolved_capture:
        errors.append("partial status must prioritize resolved selected next-task commands after the probe")
    if any("<kubectl-top-output.txt>" in command for command in partial_payload.get("nextCommands", [])[:3]):
        errors.append("partial status must not keep selected next-task placeholders before resolved commands")
    expected_resolved_kind = (
        f"python3 -B scripts/run_lightweight_cluster_smoke.py --provider kind --run "
        f"--output {partial_dir / 'reports' / '02-lightweight-cluster-smoke-lightweight-kind.json'}"
    )
    if expected_resolved_kind in partial_payload.get("nextCommands", []):
        errors.append("partial status must not recommend missing-tool prepared queue commands")
    for placeholder in ("<path>", "<kubectl-top-output.txt>", "<external-evidence.json>", "<evidence-dir>"):
        if any(placeholder in command for command in partial_payload.get("nextCommands", [])):
            errors.append(f"partial status must not keep prepared queue placeholder in next commands: {placeholder}")
    next_task = partial_payload.get("nextTask") or {}
    selected = next_task.get("selected") or {}
    if next_task.get("schemaVersion") != NEXT_TASK_SCHEMA:
        errors.append("partial status must include next-task schema")
    if next_task.get("queueSource") != "prepared-live-validation-queue":
        errors.append("partial status must preserve next-task queue source")
    if next_task.get("queueSourceOrigin") != "explicit-source-worklist":
        errors.append("partial status must report explicit next-task queue source origin")
    if next_task.get("queueConsistency", {}).get("status") != "matched":
        errors.append("partial status must report matched next-task queue consistency")
    next_task_summary = next_task.get("summary", {})
    if next_task_summary.get("files") != 3:
        errors.append("partial status must summarize three selected next-task file references")
    if next_task_summary.get("existingFiles") != 2 or next_task_summary.get("missingFiles") != 1:
        errors.append("partial status must report next-task file readiness")
    if selected.get("id") != "01-controller-resource-budget":
        errors.append("partial status must preserve selected next task")
    next_task_run = partial_payload.get("nextTaskRun") or {}
    if next_task_run.get("schemaVersion") != NEXT_TASK_RUN_SCHEMA:
        errors.append("partial status must include next-task-run schema")
    if next_task_run.get("queueSource") != "prepared-live-validation-queue":
        errors.append("partial status must preserve next-task-run queue source")
    if next_task_run.get("queueSourceOrigin") != "inferred-live-validation-queue":
        errors.append("partial status must report inferred next-task-run queue source origin")
    if next_task_run.get("nextTaskConsistency", {}).get("status") != "matched":
        errors.append("partial status must report matched next-task-run consistency")
    if next_task_run.get("status") != "failed" or next_task_run.get("mode") != "run":
        errors.append("partial status must preserve next-task-run status")
    if next_task_run.get("summary", {}).get("ran") != 2:
        errors.append("partial status must summarize next-task-run command count")
    failure = next_task_run.get("failure") or {}
    if failure.get("message") != "error: test cluster unavailable":
        errors.append("partial status must preserve next-task-run failure message")
    environment_probe = partial_payload.get("environmentProbe") or {}
    if environment_probe.get("schemaVersion") != ENVIRONMENT_PROBE_SCHEMA:
        errors.append("partial status must include environment-probe schema")
    if environment_probe.get("clusterAccess") != "not-run":
        errors.append("partial status must preserve default environment probe status")
    environment_blockers = partial_payload.get("environmentBlockers") or {}
    if environment_blockers.get("schemaVersion") != ENVIRONMENT_BLOCKERS_SCHEMA:
        errors.append("partial status must include environment-blockers schema")
    if environment_blockers.get("summary", {}).get("blockedByEnvironment") != 0:
        errors.append("partial status must summarize environment blockers")
    advance = partial_payload.get("versionIterationAdvance") or {}
    if advance.get("schemaVersion") != ADVANCE_SCHEMA:
        errors.append("partial status must include version-iteration-advance schema")
    if advance.get("queueSource") != "prepared-live-validation-queue":
        errors.append("partial status must preserve version-iteration-advance queue source")
    if advance.get("queueSourceOrigin") != "inferred-live-validation-queue":
        errors.append("partial status must report inferred version-iteration-advance queue source origin")
    if advance.get("nextTaskConsistency", {}).get("status") != "mismatched":
        errors.append("partial status must report stale version-iteration-advance consistency")
    if advance.get("nextTaskConsistency", {}).get("mismatches") != ["id"]:
        errors.append("partial status must report version-iteration-advance id mismatch")
    if advance.get("status") != "passed" or advance.get("runId") != "test-advance":
        errors.append("partial status must preserve version-iteration-advance status")
    resolved_next = "\n".join(selected.get("resolvedCommands", []))
    if "raw/01-controller-resource-budget-kubectl-top.txt" not in resolved_next:
        errors.append("partial status must preserve resolved next-task raw path")
    files = selected.get("files", [])
    if not any(
        "raw/01-controller-resource-budget-kubectl-top.txt" in str(item.get("path"))
        and item.get("exists") is True
        for item in files
    ):
        errors.append("partial status must mark the raw capture file present")
    if not any(item.get("role") == "output" and item.get("exists") is False for item in files):
        errors.append("partial status must mark the output file missing")
    if partial_text.returncode != 0 or "next-task: 01-controller-resource-budget" not in partial_text.stdout:
        errors.append("partial text status must print the selected next task")
    if "next-task-files: 2/3" not in partial_text.stdout:
        errors.append("partial text status must print next-task file readiness")
    if "next-task-queue-source: prepared-live-validation-queue" not in partial_text.stdout:
        errors.append("partial text status must print next-task queue source")
    if "next-task-queue-source-origin: explicit-source-worklist" not in partial_text.stdout:
        errors.append("partial text status must print next-task queue source origin")
    if "next-task-queue-consistency: matched" not in partial_text.stdout:
        errors.append("partial text status must print matched next-task queue consistency")
    if "next-task-run: failed" not in partial_text.stdout or "next-task-run-ran: 2" not in partial_text.stdout:
        errors.append("partial text status must print next-task-run status")
    if "next-task-run-queue-source: prepared-live-validation-queue" not in partial_text.stdout:
        errors.append("partial text status must print next-task-run queue source")
    if "next-task-run-queue-source-origin: inferred-live-validation-queue" not in partial_text.stdout:
        errors.append("partial text status must print next-task-run queue source origin")
    if "next-task-run-consistency: matched" not in partial_text.stdout:
        errors.append("partial text status must print matched next-task-run consistency")
    if "next-task-run-error: error: test cluster unavailable" not in partial_text.stdout:
        errors.append("partial text status must print next-task-run failure message")
    if f"next: {expected_probe_command}" not in partial_text.stdout:
        errors.append("partial text status must print the environment probe next command")
    if f"next: {expected_resolved_capture}" not in partial_text.stdout:
        errors.append("partial text status must print resolved selected next-task command")
    if "environment-probe: not-run" not in partial_text.stdout:
        errors.append("partial text status must print environment probe status")
    if "environment-blockers: 0" not in partial_text.stdout:
        errors.append("partial text status must print environment blocker count")
    if "version-iteration-advance: passed" not in partial_text.stdout:
        errors.append("partial text status must print advance status")
    if "version-iteration-advance-queue-source: prepared-live-validation-queue" not in partial_text.stdout:
        errors.append("partial text status must print advance queue source")
    if "version-iteration-advance-queue-source-origin: inferred-live-validation-queue" not in partial_text.stdout:
        errors.append("partial text status must print advance queue source origin")
    if "version-iteration-advance-consistency: mismatched" not in partial_text.stdout:
        errors.append("partial text status must print stale advance consistency")
    if "version-iteration-advance-mismatches: id" not in partial_text.stdout:
        errors.append("partial text status must print advance mismatch fields")

    if next_task_build_payload.get("schemaVersion") != NEXT_TASK_BUILD_SCHEMA:
        errors.append("next-task evidence build schemaVersion mismatch")
    if next_task_build_payload.get("summary", {}).get("status") != "passed":
        errors.append("next-task evidence build must pass with prepared raw input")
    if next_task_build_payload.get("summary", {}).get("buildableCommands") != 1:
        errors.append("next-task evidence build must find one local builder command")
    if next_task_build_payload.get("summary", {}).get("built") != 1:
        errors.append("next-task evidence build must create one supplemental record")
    if next_task_build_payload.get("summary", {}).get("errors") != 0:
        errors.append("next-task evidence build must not report errors")
    if not next_task_output_written:
        errors.append("next-task evidence build must write supplemental evidence output")
    if next_task_build_again.returncode != 0:
        errors.append("repeat next-task evidence build must remain idempotent")
    if "output-exists" not in next_task_build_again.stdout:
        errors.append("repeat next-task evidence build must report output-exists")
    if "skipped: 1" not in next_task_build_again.stdout:
        errors.append("repeat next-task evidence build must count one skipped output")

    after_summary = partial_after_build_payload.get("summary", {})
    if after_summary.get("supplementalEvidence") != 1:
        errors.append("post-build partial status must count one supplemental evidence record")
    after_next_task_summary = (partial_after_build_payload.get("nextTask") or {}).get("summary", {})
    if after_next_task_summary.get("existingFiles") != 3 or after_next_task_summary.get("missingFiles") != 0:
        errors.append("post-build partial status must report complete next-task file readiness")
    if partial_after_build_text.returncode != 0 or "next-task-files: 3/3" not in partial_after_build_text.stdout:
        errors.append("post-build partial text status must print complete next-task file readiness")

    blocked_probe = blocked_payload.get("environmentProbe") or {}
    blocked_blockers = blocked_payload.get("environmentBlockers") or {}
    blocked_selected = blocked_blockers.get("selected") or {}
    expected_blocked_probe_command = f"python3 -B scripts/prepare_live_evidence_directory.py {blocked_dir} --probe-environment"
    if blocked_probe.get("clusterAccess") != "unavailable":
        errors.append("blocked evidence status must preserve unavailable cluster access")
    if blocked_selected.get("nextStep") != "start or select a disposable cluster, then rerun the probe":
        errors.append("blocked evidence status must preserve selected blocker next step")
    if not blocked_payload.get("nextCommands") or blocked_payload.get("nextCommands", [None])[0] != expected_blocked_probe_command:
        errors.append("blocked evidence status must recommend rerunning the environment probe first")
    if len(blocked_payload.get("nextCommands", [])) != 1:
        errors.append("blocked evidence status must recommend only the probe rerun")
    expected_blocked_capture = (
        f"python3 -B scripts/capture_controller_resource_budget.py "
        f"--output {blocked_dir / 'raw' / '01-controller-resource-budget-kubectl-top.txt'} --run"
    )
    if expected_blocked_capture in blocked_payload.get("nextCommands", []):
        errors.append("blocked evidence status must not recommend blocked selected capture commands")
    if any("<kubectl-top-output.txt>" in command for command in blocked_payload.get("nextCommands", [])[:3]):
        errors.append("blocked evidence status must not keep selected next-task placeholders before resolved commands")
    expected_blocked_kind = (
        f"python3 -B scripts/run_lightweight_cluster_smoke.py --provider kind --run "
        f"--output {blocked_dir / 'reports' / '02-lightweight-cluster-smoke-lightweight-kind.json'}"
    )
    if expected_blocked_kind in blocked_payload.get("nextCommands", []):
        errors.append("blocked evidence status must not recommend missing-tool prepared queue commands")
    for placeholder in ("<path>", "<kubectl-top-output.txt>", "<external-evidence.json>", "<evidence-dir>"):
        if any(placeholder in command for command in blocked_payload.get("nextCommands", [])):
            errors.append(f"blocked evidence status must not keep prepared queue placeholder in next commands: {placeholder}")
    if "environment-next: start or select a disposable cluster, then rerun the probe" not in blocked_text.stdout:
        errors.append("blocked text status must print selected environment next step")

    stale_next_task = stale_payload.get("nextTask") or {}
    stale_consistency = stale_next_task.get("queueConsistency") or {}
    if stale_consistency.get("status") != "mismatched":
        errors.append("stale evidence status must report mismatched next-task queue consistency")
    if "captureStatus" not in stale_consistency.get("mismatches", []):
        errors.append("stale evidence status must identify captureStatus mismatch")
    if "next-task-queue-consistency: mismatched" not in stale_text.stdout:
        errors.append("stale text status must print mismatched next-task queue consistency")
    if "next-task-queue-mismatches: captureStatus" not in stale_text.stdout:
        errors.append("stale text status must print next-task queue mismatch fields")

    if complete_payload.get("summary", {}).get("status") != "complete":
        errors.append("full evidence directory must report complete")
    if complete_payload.get("summary", {}).get("liveReports") != 10:
        errors.append("full evidence directory must count ten live reports")
    if complete_payload.get("summary", {}).get("supplementalEvidence") != 3:
        errors.append("full evidence directory must count three supplemental records")
    if complete_payload.get("summary", {}).get("coveredGates") != 16:
        errors.append("full evidence directory must cover all external gates")
    if complete_payload.get("summary", {}).get("coverageErrors") != 0:
        errors.append("full evidence directory must have no coverage errors")

    for snippet in (
        "inspect_release_evidence_directory.py",
        "build_next_task_evidence.py",
        "kube-actuary.release-evidence-status.v1",
        NEXT_TASK_SCHEMA,
        NEXT_TASK_BUILD_SCHEMA,
        NEXT_TASK_RUN_SCHEMA,
        ENVIRONMENT_PROBE_SCHEMA,
        ENVIRONMENT_BLOCKERS_SCHEMA,
        ADVANCE_SCHEMA,
        "--record",
        "release-evidence-status.json",
    ):
        if snippet not in README.read_text():
            errors.append(f"README missing release evidence status detail: {snippet}")
        if snippet not in LIVE_VALIDATION.read_text():
            errors.append(f"live validation doc missing release evidence status detail: {snippet}")

    if errors:
        print("release-evidence-status: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("release-evidence-status: passed")
    print("partial: ok")
    print("complete: ok")
    print("next-task-run: ok")
    print("environment: ok")
    print("advance: ok")
    print("record: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
