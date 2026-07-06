#!/usr/bin/env python3
"""Verify release evidence directory status inspection."""

from __future__ import annotations

import json
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


def write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload))


def write_next_task_run(evidence_dir: Path) -> None:
    write_payload(
        evidence_dir / ".kubeactuary" / "next-version-task-run.json",
        {
            "schemaVersion": NEXT_TASK_RUN_SCHEMA,
            "mode": "run",
            "status": "passed",
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
                "failed": 0,
                "validationErrors": 0,
            },
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

    if partial_payload.get("schemaVersion") != "kube-actuary.release-evidence-status.v1":
        errors.append("status schemaVersion mismatch")
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
    if partial_payload.get("summary", {}).get("status") != "partial":
        errors.append("partial evidence directory must report partial")
    if partial_payload.get("summary", {}).get("liveReports") != 1:
        errors.append("partial evidence directory must count one live report")
    if not partial_payload.get("missing", {}).get("coverage"):
        errors.append("partial status must include coverage misses")
    if not any("run_managed_kubernetes_smoke.py" in command for command in partial_payload.get("nextCommands", [])):
        errors.append("partial status must include next provider commands")
    next_task = partial_payload.get("nextTask") or {}
    selected = next_task.get("selected") or {}
    if next_task.get("schemaVersion") != NEXT_TASK_SCHEMA:
        errors.append("partial status must include next-task schema")
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
    if next_task_run.get("status") != "passed" or next_task_run.get("mode") != "run":
        errors.append("partial status must preserve next-task-run status")
    if next_task_run.get("summary", {}).get("ran") != 2:
        errors.append("partial status must summarize next-task-run command count")
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
    if "next-task-run: passed" not in partial_text.stdout or "next-task-run-ran: 2" not in partial_text.stdout:
        errors.append("partial text status must print next-task-run status")
    if "environment-probe: not-run" not in partial_text.stdout:
        errors.append("partial text status must print environment probe status")
    if "environment-blockers: 0" not in partial_text.stdout:
        errors.append("partial text status must print environment blocker count")
    if "version-iteration-advance: passed" not in partial_text.stdout:
        errors.append("partial text status must print advance status")

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
