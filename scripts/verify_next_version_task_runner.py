#!/usr/bin/env python3
"""Verify the selected next-version task runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "scripts" / "prepare_live_evidence_directory.py"
RUNNER = ROOT / "scripts" / "run_next_version_task.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
LIVE_VALIDATION = ROOT / "docs" / "live-validation.md"


def run_script(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(script), *args],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def fake_tool_env(path: Path) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    kubectl = path / "kubectl"
    kubectl.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['top', 'pod']:\n"
        "    print('POD NAME CPU(cores) MEMORY(bytes)')\n"
        "    print('controller-0 controller 12m 41Mi')\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(2)\n"
    )
    kubectl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', '')}"
    return env


def fake_failing_tool_env(path: Path) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    kubectl = path / "kubectl"
    kubectl.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('Unable to connect to the server: test cluster unavailable', file=sys.stderr)\n"
        "raise SystemExit(1)\n"
    )
    kubectl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{path}{os.pathsep}{env.get('PATH', '')}"
    return env


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        blocked_dir = tmpdir / "blocked"
        missing_tools_dir = tmpdir / "missing-tools"
        markdown_dir = tmpdir / "markdown"
        recorded_dir = tmpdir / "recorded"
        failing_dir = tmpdir / "failing"
        unprepared_dir = tmpdir / "unprepared"
        unprepared = run_script(RUNNER, str(unprepared_dir))
        if unprepared.returncode == 0:
            errors.append("runner must fail for an unprepared evidence directory")
        if "prepare_live_evidence_directory.py" not in unprepared.stdout:
            errors.append("runner unprepared error must include the prepare command")
        prepared = run_script(PREPARE, str(evidence_dir))
        raw = evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt"
        supplemental = evidence_dir / "supplemental" / "01-controller-resource-budget-external-2.json"
        if prepared.returncode != 0:
            errors.append(f"prepare evidence dir failed: {prepared.stderr.strip() or prepared.stdout.strip()}")

        plan = run_script(RUNNER, str(evidence_dir))
        plan_markdown = run_script(RUNNER, str(evidence_dir), "--format", "markdown")
        if plan.returncode != 0:
            errors.append(f"runner plan failed: {plan.stderr.strip() or plan.stdout.strip()}")
        if "next-version-task-run: plan" not in plan.stdout:
            errors.append("runner plan must report plan status")
        if "queue-source: prepared-live-validation-queue" not in plan.stdout:
            errors.append("runner plan text must show prepared queue source")
        if plan_markdown.returncode != 0:
            errors.append(f"runner plan Markdown failed: {plan_markdown.stderr.strip() or plan_markdown.stdout.strip()}")
        for snippet in (
            "# KubeActuary Next Version Task Run",
            "Mode: `plan`",
            "Status: `plan`",
            "Queue source: `prepared-live-validation-queue`",
            "## Commands",
        ):
            if snippet not in plan_markdown.stdout:
                errors.append(f"runner plan Markdown should include: {snippet}")
        if raw.exists() or supplemental.exists():
            errors.append("runner plan must not write evidence files")

        blocked_metadata = blocked_dir / ".kubeactuary"
        blocked_metadata.mkdir(parents=True)
        blocked_raw = blocked_dir / "raw" / "blocked-kubectl-top.txt"
        blocked_supplemental = blocked_dir / "supplemental" / "blocked-external.json"
        blocked_next_step = "start or select a disposable cluster, then rerun the probe"
        (blocked_metadata / "next-version-task.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "kube-actuary.next-version-task.v1",
                    "selected": {
                        "id": "blocked-controller-resource-budget",
                        "version": "Current Baseline",
                        "item": "Controller resource budget",
                        "kind": "controller-resource-budget",
                        "captureStatus": "blocked-by-environment",
                        "environmentStatus": "cluster-unavailable",
                        "nextStep": blocked_next_step,
                        "resolvedCommands": [
                            (
                                "python3 -B scripts/capture_controller_resource_budget.py "
                                f"--output {blocked_raw.as_posix()} --run"
                            ),
                            (
                                "python3 -B scripts/build_external_evidence.py "
                                f"--kind controller-resource-budget --source {blocked_raw.as_posix()} "
                                f"--output {blocked_supplemental.as_posix()}"
                            ),
                        ],
                    },
                }
            )
            + "\n"
        )
        blocked = run_script(RUNNER, str(blocked_dir), "--run", "--format", "json")
        blocked_text = run_script(RUNNER, str(blocked_dir), "--run")
        blocked_markdown = run_script(RUNNER, str(blocked_dir), "--run", "--format", "markdown")
        blocked_record = run_script(RUNNER, str(blocked_dir), "--run", "--record", "--format", "json")
        blocked_record_json = blocked_dir / ".kubeactuary" / "next-version-task-run.json"
        blocked_record_md = blocked_dir / ".kubeactuary" / "next-version-task-run.md"
        if blocked.returncode != 0:
            errors.append(f"blocked runner should not execute or fail: {blocked.stderr.strip() or blocked.stdout.strip()}")
            blocked_payload = {}
        else:
            blocked_payload = json.loads(blocked.stdout)
        blocked_summary = blocked_payload.get("summary", {})
        if blocked_payload.get("status") != "blocked-by-environment" or blocked_summary.get("ran") != 0:
            errors.append("blocked runner must report blocked-by-environment with zero executed commands")
        if blocked_raw.exists() or blocked_supplemental.exists():
            errors.append("blocked runner must not create raw or supplemental evidence files")
        if blocked_payload.get("blocker", {}).get("message") != blocked_next_step:
            errors.append("blocked runner must preserve the selected blocker next step")
        if f"blocker: {blocked_next_step}" not in blocked_text.stdout:
            errors.append("blocked runner text output must print the blocker summary")
        if blocked_markdown.returncode != 0:
            errors.append("blocked runner Markdown should return zero while preserving blocked status")
        if f"- `{blocked_next_step}`" not in blocked_markdown.stdout:
            errors.append("blocked runner Markdown must print the blocker summary")
        if blocked_record.returncode != 0:
            errors.append("blocked runner --record should return zero while preserving blocked status")
        if not blocked_record_json.is_file() or not blocked_record_md.is_file():
            errors.append("blocked runner --record must persist zero-run reports")
        else:
            blocked_record_payload = json.loads(blocked_record_json.read_text())
            if blocked_record_payload.get("summary", {}).get("ran") != 0:
                errors.append("blocked runner recorded JSON must preserve zero-run summary")
            if blocked_next_step not in blocked_record_md.read_text():
                errors.append("blocked runner recorded Markdown must preserve blocker summary")

        missing_metadata = missing_tools_dir / ".kubeactuary"
        missing_metadata.mkdir(parents=True)
        missing_output = missing_tools_dir / "reports" / "missing-helm.json"
        (missing_metadata / "next-version-task.json").write_text(
            json.dumps(
                {
                    "schemaVersion": "kube-actuary.next-version-task.v1",
                    "selected": {
                        "id": "missing-helm",
                        "version": "0.5.0",
                        "item": "Helm chart",
                        "kind": "helm",
                        "captureStatus": "missing-tools",
                        "missingTools": ["helm"],
                        "nextStep": "install missing tools or run on a host that has them",
                        "resolvedCommands": [
                            (
                                "python3 -B scripts/run_helm_smoke.py "
                                f"--run --output {missing_output.as_posix()}"
                            ),
                        ],
                    },
                }
            )
            + "\n"
        )
        missing = run_script(RUNNER, str(missing_tools_dir), "--run", "--format", "json")
        missing_record = run_script(RUNNER, str(missing_tools_dir), "--run", "--record", "--format", "json")
        missing_record_json = missing_tools_dir / ".kubeactuary" / "next-version-task-run.json"
        missing_record_md = missing_tools_dir / ".kubeactuary" / "next-version-task-run.md"
        if missing.returncode == 0:
            errors.append("missing-tools runner must return non-zero while avoiding command execution")
            missing_payload = {}
        else:
            missing_payload = json.loads(missing.stdout)
        missing_summary = missing_payload.get("summary", {})
        if missing_payload.get("status") != "missing-tools" or missing_summary.get("ran") != 0:
            errors.append("missing-tools runner must report missing-tools with zero executed commands")
        if missing_output.exists():
            errors.append("missing-tools runner must not create report evidence files")
        if missing_payload.get("blocker", {}).get("message") != "missing tools: helm":
            errors.append("missing-tools runner must preserve the missing tool summary")
        if missing_record.returncode == 0:
            errors.append("missing-tools runner --record must keep a non-zero exit status")
        if not missing_record_json.is_file() or not missing_record_md.is_file():
            errors.append("missing-tools runner --record must persist zero-run reports")
        else:
            missing_record_payload = json.loads(missing_record_json.read_text())
            if missing_record_payload.get("summary", {}).get("ran") != 0:
                errors.append("missing-tools runner recorded JSON must preserve zero-run summary")
            if "missing tools: helm" not in missing_record_md.read_text():
                errors.append("missing-tools runner recorded Markdown must preserve missing-tool summary")

        run_env = fake_tool_env(tmpdir / "tools")
        failing_env = fake_failing_tool_env(tmpdir / "failing-tools")
        markdown_prepared = run_script(PREPARE, str(markdown_dir))
        run_markdown = run_script(RUNNER, str(markdown_dir), "--run", "--format", "markdown", env=run_env)
        run = run_script(RUNNER, str(evidence_dir), "--run", "--format", "json", env=run_env)
        if markdown_prepared.returncode != 0:
            errors.append(f"markdown evidence dir prepare failed: {markdown_prepared.stderr.strip() or markdown_prepared.stdout.strip()}")
        if run_markdown.returncode != 0:
            errors.append(f"runner run Markdown failed: {run_markdown.stderr.strip() or run_markdown.stdout.strip()}")
        for snippet in (
            "Mode: `run`",
            "Status: `passed`",
            "Queue source: `prepared-live-validation-queue`",
            "## Run Records",
            "exit code: 0",
        ):
            if snippet not in run_markdown.stdout:
                errors.append(f"runner run Markdown should include: {snippet}")
        if run.returncode != 0:
            errors.append(f"runner execution failed: {run.stderr.strip() or run.stdout.strip()}")
            payload = {}
        else:
            payload = json.loads(run.stdout)
        if payload.get("schemaVersion") != "kube-actuary.next-version-task-run.v1":
            errors.append("runner schemaVersion mismatch")
        if payload.get("status") != "passed" or payload.get("mode") != "run":
            errors.append("runner execution must report passed run mode")
        if payload.get("clusterWrites") != "disabled-or-server-side-dry-run-only":
            errors.append("runner must preserve low-impact cluster write contract")
        if payload.get("queueSource") != "prepared-live-validation-queue":
            errors.append("runner must preserve the prepared queue source")
        if payload.get("nextTask", {}).get("queueSource") != "prepared-live-validation-queue":
            errors.append("runner next-task summary must preserve the prepared queue source")
        summary = payload.get("summary", {})
        if summary.get("commands") != 2 or summary.get("ran") != 2 or summary.get("failed") != 0:
            errors.append("runner must execute the two selected resource-budget commands")
        if not raw.is_file() or "controller-0 controller 12m 41Mi" not in raw.read_text():
            errors.append("runner must capture raw kubectl top evidence")
        if not supplemental.is_file():
            errors.append("runner must build supplemental resource-budget evidence")
        else:
            supplemental_payload = json.loads(supplemental.read_text())
            if supplemental_payload.get("kind") != "controller-resource-budget" or supplemental_payload.get("ok") is not True:
                errors.append("runner supplemental evidence must be passing controller-resource-budget evidence")

        failing_prepared = run_script(PREPARE, str(failing_dir))
        failing = run_script(RUNNER, str(failing_dir), "--run", "--format", "json", env=failing_env)
        failing_text = run_script(RUNNER, str(failing_dir), "--run", env=failing_env)
        failing_record = run_script(RUNNER, str(failing_dir), "--run", "--record", "--format", "json", env=failing_env)
        failing_record_json = failing_dir / ".kubeactuary" / "next-version-task-run.json"
        failing_record_md = failing_dir / ".kubeactuary" / "next-version-task-run.md"
        if failing_prepared.returncode != 0:
            errors.append(f"failing evidence dir prepare failed: {failing_prepared.stderr.strip() or failing_prepared.stdout.strip()}")
        if failing.returncode == 0:
            errors.append("runner failure scenario must return non-zero")
            failing_payload = {}
        else:
            failing_payload = json.loads(failing.stdout)
        failure = failing_payload.get("failure") or {}
        if failing_payload.get("status") != "failed" or failure.get("message") != "error: Unable to connect to the server: test cluster unavailable":
            errors.append("runner failure summary must preserve the command failure message")
        if "failure: error: Unable to connect to the server: test cluster unavailable" not in failing_text.stdout:
            errors.append("runner text output must print the failure summary")
        if failing_record.returncode == 0:
            errors.append("runner recorded failure scenario must return non-zero")
        if not failing_record_json.is_file() or not failing_record_md.is_file():
            errors.append("runner --record must persist failed run reports")
        else:
            failing_record_payload = json.loads(failing_record_json.read_text())
            if (failing_record_payload.get("failure") or {}).get("message") != failure.get("message"):
                errors.append("runner recorded failure JSON must preserve the failure summary")
            if "Unable to connect to the server: test cluster unavailable" not in failing_record_md.read_text():
                errors.append("runner recorded failure Markdown must preserve the failure summary")

        advanced = run_script(PREPARE, str(evidence_dir), "--skip-complete-evidence")
        next_task_path = evidence_dir / ".kubeactuary" / "next-version-task.json"
        if advanced.returncode != 0:
            errors.append(f"skip-complete prepare failed: {advanced.stderr.strip() or advanced.stdout.strip()}")
        else:
            next_task = json.loads(next_task_path.read_text())
            selected = next_task.get("selected") or {}
            if next_task.get("summary", {}).get("skippedCompleteEvidence") != 1:
                errors.append("runner evidence should make one task skippable")
            if selected.get("id") == "01-controller-resource-budget":
                errors.append("skip-complete should advance beyond the completed resource-budget task")

        output = tmpdir / "runner-status.json"
        written = run_script(RUNNER, str(evidence_dir), "--format", "json", "--output", str(output))
        if written.returncode != 0 or not output.is_file():
            errors.append("runner must write requested status output")

        recorded_prepared = run_script(PREPARE, str(recorded_dir))
        recorded_json = recorded_dir / ".kubeactuary" / "next-version-task-run.json"
        recorded_md = recorded_dir / ".kubeactuary" / "next-version-task-run.md"
        recorded = run_script(RUNNER, str(recorded_dir), "--run", "--format", "json", "--record", env=run_env)
        if recorded_prepared.returncode != 0:
            errors.append(f"recorded evidence dir prepare failed: {recorded_prepared.stderr.strip() or recorded_prepared.stdout.strip()}")
        if recorded.returncode != 0:
            errors.append(f"runner record execution failed: {recorded.stderr.strip() or recorded.stdout.strip()}")
            recorded_stdout = {}
        else:
            recorded_stdout = json.loads(recorded.stdout)
        if "next-version-task-run: recorded" in recorded.stdout:
            errors.append("runner record notice must not corrupt JSON stdout")
        if not recorded_json.is_file() or not recorded_md.is_file():
            errors.append("runner --record must write JSON and Markdown reports")
            recorded_payload = {}
            recorded_md_text = ""
        else:
            recorded_payload = json.loads(recorded_json.read_text())
            recorded_md_text = recorded_md.read_text()
            if "# KubeActuary Next Version Task Run" not in recorded_md_text:
                errors.append("runner recorded Markdown must include the run report title")
        if recorded_payload.get("schemaVersion") != "kube-actuary.next-version-task-run.v1":
            errors.append("runner recorded JSON schemaVersion mismatch")
        if recorded_payload.get("status") != "passed" or recorded_payload.get("mode") != "run":
            errors.append("runner recorded JSON must preserve passed run status")
        if recorded_payload.get("queueSource") != "prepared-live-validation-queue":
            errors.append("runner recorded JSON must preserve prepared queue source")
        if "Queue source: `prepared-live-validation-queue`" not in recorded_md_text:
            errors.append("runner recorded Markdown must preserve prepared queue source")
        if recorded_stdout.get("schemaVersion") != recorded_payload.get("schemaVersion"):
            errors.append("runner recorded stdout and file JSON must use the same schema")

    for path in (README, README_KO, LIVE_VALIDATION):
        text = path.read_text()
        for snippet in ("run_next_version_task.py", "kube-actuary.next-version-task-run.v1", "--record"):
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing next task runner detail: {snippet}")

    if errors:
        print("next-version-task-runner: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("next-version-task-runner: passed")
    print("mode: plan,run")
    print("cluster-writes: disabled-or-server-side-dry-run-only")
    print("evidence: raw,supplemental")
    print("blocked-run: zero")
    print("record: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
