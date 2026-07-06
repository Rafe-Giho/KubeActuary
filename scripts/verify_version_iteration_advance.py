#!/usr/bin/env python3
"""Verify the version-iteration advance workflow."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADVANCE = ROOT / "scripts" / "advance_version_iteration.py"
INSPECT_HISTORY = ROOT / "scripts" / "inspect_version_history.py"
README = ROOT / "README.md"
README_KO = ROOT / "README.ko.md"
TASKBOARD = ROOT / "docs" / "release-taskboard.md"
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


def fake_tool_env(path: Path, cluster_ok: bool = True) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
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


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        history_dir = tmpdir / "history"
        blocked_evidence_dir = tmpdir / "blocked-evidence"
        blocked_history_dir = tmpdir / "blocked-history"

        plan = run_script(ADVANCE, str(evidence_dir), str(history_dir))
        plan_markdown = run_script(ADVANCE, str(evidence_dir), str(history_dir), "--format", "markdown")
        filtered_plan = run_script(
            ADVANCE,
            str(tmpdir / "filtered-plan-evidence"),
            str(tmpdir / "filtered-plan-history"),
            "--missing-tool",
            "kind",
            "--format",
            "json",
        )
        runnable_plan = run_script(
            ADVANCE,
            str(tmpdir / "runnable-plan-evidence"),
            str(tmpdir / "runnable-plan-history"),
            "--runnable-only",
            "--format",
            "json",
        )
        blocked_plan = run_script(
            ADVANCE,
            str(tmpdir / "blocked-plan-evidence"),
            str(tmpdir / "blocked-plan-history"),
            "--blocked-only",
            "--format",
            "json",
        )
        conflicting_plan = run_script(
            ADVANCE,
            str(tmpdir / "conflict-plan-evidence"),
            str(tmpdir / "conflict-plan-history"),
            "--runnable-only",
            "--blocked-only",
        )
        version_plan = run_script(
            ADVANCE,
            str(tmpdir / "version-plan-evidence"),
            str(tmpdir / "version-plan-history"),
            "--version",
            "0.4.3",
            "--format",
            "json",
        )
        version_plan_markdown = run_script(
            ADVANCE,
            str(tmpdir / "version-plan-md-evidence"),
            str(tmpdir / "version-plan-md-history"),
            "--version",
            "0.4.3",
            "--format",
            "markdown",
        )
        if plan.returncode != 0:
            errors.append(f"advance plan failed: {plan.stderr.strip() or plan.stdout.strip()}")
        if "version-iteration-advance: plan" not in plan.stdout:
            errors.append("advance plan must report plan status")
        if plan_markdown.returncode != 0:
            errors.append(f"advance plan Markdown failed: {plan_markdown.stderr.strip() or plan_markdown.stdout.strip()}")
        for snippet in (
            "# KubeActuary Version Iteration Advance",
            "Mode: `plan`",
            "Status: `plan`",
            "selected worklist: `python3 -B scripts/generate_version_worklist.py",
            "planned step: prepare live evidence directory with skip-complete evidence",
        ):
            if snippet not in plan_markdown.stdout:
                errors.append(f"advance plan Markdown should include: {snippet}")
        if evidence_dir.exists() or history_dir.exists():
            errors.append("advance plan must not create evidence or history directories")
        if filtered_plan.returncode != 0:
            errors.append(f"filtered advance plan failed: {filtered_plan.stderr.strip() or filtered_plan.stdout.strip()}")
            filtered_plan_payload = {}
        else:
            filtered_plan_payload = json.loads(filtered_plan.stdout)
        if filtered_plan_payload.get("filters", {}).get("missingTools") != ["kind"]:
            errors.append("filtered advance plan must persist missing-tool filters")
        if filtered_plan_payload.get("selected", {}).get("id") != "02-lightweight-cluster-smoke":
            errors.append("filtered advance plan should select the first kind-blocked task")
        if filtered_plan_payload.get("selected", {}).get("captureStatus") != "missing-tools":
            errors.append("filtered advance plan should preserve missing-tools capture status")
        if not any(
            "--capture-status missing-tools --missing-tool kind" in command
            for command in filtered_plan_payload.get("selected", {}).get("worklistCommands", [])
        ):
            errors.append("filtered advance plan must include selected worklist drilldown")
        if (tmpdir / "filtered-plan-evidence").exists() or (tmpdir / "filtered-plan-history").exists():
            errors.append("filtered advance plan must not create evidence or history directories")
        if runnable_plan.returncode != 0:
            errors.append(f"runnable-only advance plan failed: {runnable_plan.stderr.strip() or runnable_plan.stdout.strip()}")
            runnable_plan_payload = {}
        else:
            runnable_plan_payload = json.loads(runnable_plan.stdout)
        if runnable_plan_payload.get("filters", {}).get("runnableOnly") is not True:
            errors.append("runnable-only advance plan must persist runnable-only filter")
        if runnable_plan_payload.get("selected", {}).get("id") != "01-controller-resource-budget":
            errors.append("runnable-only advance plan should select the first runnable task")
        if runnable_plan_payload.get("selected", {}).get("captureStatus") != "tool-ready":
            errors.append("runnable-only advance plan should select tool-ready work")
        if blocked_plan.returncode != 0:
            errors.append(f"blocked-only advance plan failed: {blocked_plan.stderr.strip() or blocked_plan.stdout.strip()}")
            blocked_plan_payload = {}
        else:
            blocked_plan_payload = json.loads(blocked_plan.stdout)
        if blocked_plan_payload.get("filters", {}).get("blockedOnly") is not True:
            errors.append("blocked-only advance plan must persist blocked-only filter")
        if blocked_plan_payload.get("selected", {}).get("id") != "02-lightweight-cluster-smoke":
            errors.append("blocked-only advance plan should select the first blocked task")
        if blocked_plan_payload.get("selected", {}).get("captureStatus") != "missing-tools":
            errors.append("blocked-only advance plan should select missing-tools work")
        if conflicting_plan.returncode == 0:
            errors.append("advance plan must reject conflicting selector modes")
        if "--runnable-only and --blocked-only are mutually exclusive" not in conflicting_plan.stdout:
            errors.append("advance plan conflict should report selector mode conflict")
        if (tmpdir / "runnable-plan-evidence").exists() or (tmpdir / "blocked-plan-evidence").exists():
            errors.append("selector-mode advance plans must not create evidence directories")
        if version_plan.returncode != 0:
            errors.append(f"version advance plan failed: {version_plan.stderr.strip() or version_plan.stdout.strip()}")
            version_plan_payload = {}
        else:
            version_plan_payload = json.loads(version_plan.stdout)
        if version_plan_markdown.returncode != 0:
            errors.append(
                f"version advance plan Markdown failed: {version_plan_markdown.stderr.strip() or version_plan_markdown.stdout.strip()}"
            )
        if version_plan_payload.get("filters", {}).get("versions") != ["0.4.3"]:
            errors.append("version advance plan must persist version filters")
        if version_plan_payload.get("selected", {}).get("id") != "11-resource-budget-target-idle-50m-cpu-and-64mi-memory":
            errors.append("version advance plan should select the first 0.4.3 task")
        if version_plan_payload.get("selected", {}).get("version") != "0.4.3":
            errors.append("version advance plan should preserve selected version")
        if not any(
            "--version 0.4.3 --capture-status tool-ready" in command
            for command in version_plan_payload.get("selected", {}).get("worklistCommands", [])
        ):
            errors.append("version advance plan must include version-scoped worklist drilldown")
        if "- versions: `0.4.3`" not in version_plan_markdown.stdout:
            errors.append("version advance plan Markdown must show version filters")
        if (tmpdir / "version-plan-evidence").exists() or (tmpdir / "version-plan-history").exists():
            errors.append("version advance plan must not create evidence or history directories")

        run_env = fake_tool_env(tmpdir / "tools")
        run = run_script(
            ADVANCE,
            str(evidence_dir),
            str(history_dir),
            "--run",
            "--run-id",
            "test-advance",
            "--created-at",
            "2026-07-06T00:00:00+00:00",
            "--format",
            "json",
            env=run_env,
        )
        run_markdown = run_script(
            ADVANCE,
            str(tmpdir / "markdown-evidence"),
            str(tmpdir / "markdown-history"),
            "--run",
            "--run-id",
            "markdown-advance",
            "--created-at",
            "2026-07-06T00:00:00+00:00",
            "--format",
            "markdown",
            env=run_env,
        )
        if run.returncode != 0:
            errors.append(f"advance run failed: {run.stderr.strip() or run.stdout.strip()}")
            payload = {}
        else:
            payload = json.loads(run.stdout)
        if run_markdown.returncode != 0:
            errors.append(f"advance run Markdown failed: {run_markdown.stderr.strip() or run_markdown.stdout.strip()}")
        for snippet in (
            "Mode: `run`",
            "Status: `passed`",
            "run id: `markdown-advance`",
            "next task worklist: `python3 -B scripts/generate_version_worklist.py",
            "history runs: 2",
            "runner: `passed`",
        ):
            if snippet not in run_markdown.stdout:
                errors.append(f"advance run Markdown should include: {snippet}")
        if payload.get("schemaVersion") != "kube-actuary.version-iteration-advance.v1":
            errors.append("advance schemaVersion mismatch")
        if payload.get("status") != "passed" or payload.get("mode") != "run":
            errors.append("advance run must pass in run mode")
        if payload.get("queueSource") != "prepared-live-validation-queue":
            errors.append("advance run must preserve the prepared queue source")
        if payload.get("nextTask", {}).get("queueSource") != "prepared-live-validation-queue":
            errors.append("advance next-task summary must preserve the prepared queue source")
        advance_record = payload.get("advanceRecord") or {}
        advance_record_json = Path(advance_record.get("json", ""))
        advance_record_md = Path(advance_record.get("markdown", ""))
        if not advance_record_json.is_file() or not advance_record_md.is_file():
            errors.append("advance must record its JSON and Markdown status reports")
            advance_record_payload = {}
            advance_record_md_text = ""
        else:
            advance_record_payload = json.loads(advance_record_json.read_text())
            advance_record_md_text = advance_record_md.read_text()
            if "# KubeActuary Version Iteration Advance" not in advance_record_md_text:
                errors.append("advance Markdown record must include the report title")
        if advance_record_payload.get("schemaVersion") != "kube-actuary.version-iteration-advance.v1":
            errors.append("advance recorded JSON schemaVersion mismatch")
        if advance_record_payload.get("status") != "passed":
            errors.append("advance recorded JSON must preserve passing status")
        if advance_record_payload.get("queueSource") != "prepared-live-validation-queue":
            errors.append("advance recorded JSON must preserve prepared queue source")
        if "Queue source: `prepared-live-validation-queue`" not in advance_record_md_text:
            errors.append("advance recorded Markdown must preserve prepared queue source")
        if payload.get("runner", {}).get("status") != "passed":
            errors.append("advance must include a passing next-task runner result")
        if payload.get("runner", {}).get("queueSource") != "prepared-live-validation-queue":
            errors.append("advance runner result must preserve prepared queue source")
        runner_record = payload.get("runnerRecord") or {}
        runner_record_json = Path(runner_record.get("json", ""))
        runner_record_md = Path(runner_record.get("markdown", ""))
        if not runner_record_json.is_file() or not runner_record_md.is_file():
            errors.append("advance must record next-task runner JSON and Markdown reports")
            runner_record_payload = {}
        else:
            runner_record_payload = json.loads(runner_record_json.read_text())
            if "# KubeActuary Next Version Task Run" not in runner_record_md.read_text():
                errors.append("advance runner record Markdown must include the run report title")
        if runner_record_payload.get("schemaVersion") != "kube-actuary.next-version-task-run.v1":
            errors.append("advance runner record schemaVersion mismatch")
        if runner_record_payload.get("status") != "passed":
            errors.append("advance runner record must preserve passing runner status")
        if runner_record_payload.get("queueSource") != "prepared-live-validation-queue":
            errors.append("advance runner record must preserve prepared queue source")
        if payload.get("before", {}).get("runId") != "test-advance-before":
            errors.append("advance must record before history run")
        if payload.get("after", {}).get("runId") != "test-advance-after":
            errors.append("advance must record after history run")
        after_summary = payload.get("after", {}).get("summary", {})
        if after_summary.get("completeEvidenceItems", 0) < 1:
            errors.append("advance after run must record completed evidence item")
        diff_summary = payload.get("after", {}).get("diffSummary", {})
        if diff_summary.get("existingEvidenceFilesDelta", 0) < 3:
            errors.append("advance after diff must record evidence file growth")
        if payload.get("nextTask", {}).get("skippedCompleteEvidence") != 1:
            errors.append("advance must refresh next-task artifacts past completed evidence")
        if not payload.get("nextTask", {}).get("worklistCommands"):
            errors.append("advance must include refreshed next-task worklist drilldowns")
        if payload.get("history", {}).get("runs") != 2:
            errors.append("advance history status must include two runs")
        if payload.get("history", {}).get("latestQueueSource") != "prepared-live-validation-queue":
            errors.append("advance history status must preserve prepared queue source")

        raw = evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt"
        supplemental = evidence_dir / "supplemental" / "01-controller-resource-budget-external-2.json"
        if not raw.is_file() or not supplemental.is_file():
            errors.append("advance run must leave raw and supplemental evidence files")
        index = history_dir / "index.json"
        if not index.is_file():
            errors.append("advance run must write history index")
        else:
            index_payload = json.loads(index.read_text())
            if len(index_payload.get("runs", [])) != 2:
                errors.append("history index must contain before and after runs")

        inspect = run_script(INSPECT_HISTORY, str(history_dir))
        if inspect.returncode != 0:
            errors.append(f"history inspect failed after advance: {inspect.stderr.strip() or inspect.stdout.strip()}")
        if "version-iteration-history-status: valid" not in inspect.stdout:
            errors.append("history inspect must report valid status")

        blocked_only_run = run_script(
            ADVANCE,
            str(tmpdir / "blocked-only-run-evidence"),
            str(tmpdir / "blocked-only-run-history"),
            "--blocked-only",
            "--run",
            "--run-id",
            "blocked-only-advance",
            "--created-at",
            "2026-07-06T00:00:00+00:00",
            "--format",
            "json",
        )
        if blocked_only_run.returncode != 0:
            errors.append(f"blocked-only advance run should exit cleanly: {blocked_only_run.stderr.strip() or blocked_only_run.stdout.strip()}")
            blocked_only_payload = {}
        else:
            blocked_only_payload = json.loads(blocked_only_run.stdout)
        if blocked_only_payload.get("status") != "missing-tools":
            errors.append("blocked-only advance run should preserve missing-tools status")
        if blocked_only_payload.get("filters", {}).get("blockedOnly") is not True:
            errors.append("blocked-only advance run should persist blocked-only filter")
        if blocked_only_payload.get("nextTask", {}).get("selected") != "02-lightweight-cluster-smoke":
            errors.append("blocked-only advance run should record the selected blocked task")
        if blocked_only_payload.get("runner", {}).get("summary", {}).get("ran") != 0:
            errors.append("blocked-only advance run must not execute blocked evidence commands")
        blocked_only_runner = Path((blocked_only_payload.get("runnerRecord") or {}).get("json", ""))
        if not blocked_only_runner.is_file():
            errors.append("blocked-only advance run must write a runner record")
        else:
            blocked_only_runner_payload = json.loads(blocked_only_runner.read_text())
            if blocked_only_runner_payload.get("status") != "missing-tools":
                errors.append("blocked-only runner record should preserve missing-tools status")
            if blocked_only_runner_payload.get("summary", {}).get("ran") != 0:
                errors.append("blocked-only runner record should preserve zero executed commands")
        if (tmpdir / "blocked-only-run-evidence" / "reports" / "02-lightweight-cluster-smoke-lightweight-kind.json").exists():
            errors.append("blocked-only advance run must not capture lightweight smoke evidence")

        blocked_env = fake_tool_env(tmpdir / "blocked-tools", cluster_ok=False)
        blocked_kubectl = str(tmpdir / "blocked-tools" / "kubectl")
        blocked = run_script(
            ADVANCE,
            str(blocked_evidence_dir),
            str(blocked_history_dir),
            "--run",
            "--probe-environment",
            "--kubectl",
            blocked_kubectl,
            "--version",
            "0.4.3",
            "--capture-status",
            "blocked-by-environment",
            "--run-id",
            "blocked-advance",
            "--created-at",
            "2026-07-06T00:00:00+00:00",
            "--format",
            "json",
            env=blocked_env,
        )
        if blocked.returncode != 0:
            errors.append(f"blocked advance should exit cleanly: {blocked.stderr.strip() or blocked.stdout.strip()}")
            blocked_payload = {}
        else:
            blocked_payload = json.loads(blocked.stdout)
        if blocked_payload.get("status") != "blocked-by-environment":
            errors.append("probe advance must report blocked-by-environment without running evidence commands")
        if blocked_payload.get("filters", {}).get("captureStatuses") != ["blocked-by-environment"]:
            errors.append("probe-blocked advance must persist capture-status filters")
        if blocked_payload.get("filters", {}).get("versions") != ["0.4.3"]:
            errors.append("probe-blocked advance must persist version filters")
        if blocked_payload.get("nextTask", {}).get("captureStatus") != "blocked-by-environment":
            errors.append("probe-blocked advance next-task must preserve filtered capture status")
        blocked_next_step = "start or select a disposable cluster, then rerun the probe"
        if blocked_payload.get("nextTask", {}).get("environmentStatus") != "cluster-unavailable":
            errors.append("probe-blocked advance next-task must preserve environment status")
        if blocked_payload.get("nextTask", {}).get("nextStep") != blocked_next_step:
            errors.append("probe-blocked advance next-task must preserve the blocker next step")
        blocked_streak = blocked_payload.get("latestBlockerStreak") or {}
        blocked_streak_signature = blocked_streak.get("signature") or {}
        if blocked_streak.get("streak") != 2 or blocked_streak.get("status") != "repeated":
            errors.append("probe-blocked advance must preserve latest repeated blocker streak")
        if blocked_streak_signature.get("id") != "11-resource-budget-target-idle-50m-cpu-and-64mi-memory":
            errors.append("probe-blocked advance must preserve blocker streak task id")
        if blocked_streak_signature.get("environmentReason") != "command-failed":
            errors.append("probe-blocked advance must preserve blocker streak reason")
        if blocked_payload.get("after", {}).get("runId") != "blocked-advance-blocked":
            errors.append("probe-blocked advance must record a blocked follow-up history snapshot")
        blocked_diff = blocked_payload.get("after", {}).get("diffSummary", {})
        if blocked_diff.get("captureReadyDelta") != 0 or blocked_diff.get("blockedByEnvironmentDelta") != 0:
            errors.append("probe-blocked follow-up history snapshot should preserve zero evidence-state delta")
        blocked_runner = blocked_payload.get("runner") or {}
        if blocked_runner.get("status") != "blocked-by-environment":
            errors.append("probe-blocked advance must record blocked next-task runner status")
        if blocked_runner.get("summary", {}).get("ran") != 0:
            errors.append("probe-blocked advance must not run evidence commands")
        blocked_runner_record = blocked_payload.get("runnerRecord") or {}
        blocked_runner_json = Path(blocked_runner_record.get("json", ""))
        if not blocked_runner_json.is_file():
            errors.append("probe-blocked advance must write a blocked runner record")
        else:
            blocked_runner_payload = json.loads(blocked_runner_json.read_text())
            if blocked_runner_payload.get("status") != "blocked-by-environment":
                errors.append("probe-blocked runner record must preserve blocked status")
            if blocked_runner_payload.get("summary", {}).get("ran") != 0:
                errors.append("probe-blocked runner record must preserve zero executed commands")
        blocked_advance_record = blocked_payload.get("advanceRecord") or {}
        blocked_advance_json = Path(blocked_advance_record.get("json", ""))
        blocked_advance_md = Path(blocked_advance_record.get("markdown", ""))
        if not blocked_advance_json.is_file() or not blocked_advance_md.is_file():
            errors.append("probe-blocked advance must record its blocked status")
        else:
            blocked_advance_payload = json.loads(blocked_advance_json.read_text())
            blocked_advance_md_text = blocked_advance_md.read_text()
            if blocked_advance_payload.get("status") != "blocked-by-environment":
                errors.append("probe-blocked advance record must preserve blocked status")
            if blocked_advance_payload.get("nextTask", {}).get("environmentStatus") != "cluster-unavailable":
                errors.append("probe-blocked advance record must preserve environment status")
            blocked_record_streak = blocked_advance_payload.get("latestBlockerStreak") or {}
            if blocked_record_streak.get("streak") != 2 or blocked_record_streak.get("status") != "repeated":
                errors.append("probe-blocked advance record must preserve latest blocker streak")
            if not any(
                "--version 0.4.3 --capture-status blocked-by-environment --environment-status cluster-unavailable" in command
                for command in blocked_advance_payload.get("nextTask", {}).get("worklistCommands", [])
            ):
                errors.append("probe-blocked advance record must include selected worklist drilldown")
            if "next task environment: `cluster-unavailable`" not in blocked_advance_md_text:
                errors.append("probe-blocked advance Markdown must show environment status")
            if f"next task next step: {blocked_next_step}" not in blocked_advance_md_text:
                errors.append("probe-blocked advance Markdown must show the blocker next step")
            if "latest blocker streak: `2` (repeated)" not in blocked_advance_md_text:
                errors.append("probe-blocked advance Markdown must show latest blocker streak")
            if "next task worklist: `python3 -B scripts/generate_version_worklist.py" not in blocked_advance_md_text:
                errors.append("probe-blocked advance Markdown must show selected worklist drilldown")
        if blocked_payload.get("history", {}).get("runs") != 2:
            errors.append("probe-blocked advance must record before and blocked history runs")
        if blocked_payload.get("history", {}).get("latestRunId") != "blocked-advance-blocked":
            errors.append("probe-blocked advance history must make the blocked snapshot latest")
        if blocked_payload.get("history", {}).get("latestQueueSource") != "prepared-live-validation-queue":
            errors.append("probe-blocked advance history must preserve prepared queue source")
        if (blocked_evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt").exists():
            errors.append("probe-blocked advance must not capture raw evidence")
        blocked_history_status = run_script(INSPECT_HISTORY, str(blocked_history_dir))
        if blocked_history_status.returncode != 0:
            errors.append(
                f"probe-blocked history inspect failed: "
                f"{blocked_history_status.stderr.strip() or blocked_history_status.stdout.strip()}"
            )
        else:
            for snippet in (
                "next-command: python3 -B scripts/advance_version_iteration.py",
                "--version 0.4.3 --probe-environment",
                "--capture-status blocked-by-environment --run",
                "latest-blocker-streak: 2",
                "latest-blocker-status: repeated",
            ):
                if snippet not in blocked_history_status.stdout:
                    errors.append(f"probe-blocked history next command must preserve filters: {snippet}")

        output = tmpdir / "advance.json"
        written = run_script(ADVANCE, str(evidence_dir), str(history_dir / "plan-only"), "--format", "json", "--output", str(output))
        if written.returncode != 0 or not output.is_file():
            errors.append("advance plan must write requested output file")

    for path in (README, README_KO, TASKBOARD, LIVE_VALIDATION):
        text = path.read_text()
        for snippet in (
            "advance_version_iteration.py",
            "kube-actuary.version-iteration-advance.v1",
            "next-version-task-run.json",
            "version-iteration-advance.json",
            "--missing-tool",
            "--runnable-only",
            "--blocked-only",
        ):
            if snippet not in text:
                errors.append(f"{path.relative_to(ROOT)} missing advance workflow detail: {snippet}")

    if errors:
        print("version-iteration-advance: failed")
        for error in errors:
            print(f"error: {error}")
        return 1

    print("version-iteration-advance: passed")
    print("mode: plan,run")
    print("history-runs: 2")
    print("evidence: raw,supplemental")
    print("runner-record: metadata")
    print("advance-record: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
