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


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        history_dir = tmpdir / "history"

        plan = run_script(ADVANCE, str(evidence_dir), str(history_dir))
        if plan.returncode != 0:
            errors.append(f"advance plan failed: {plan.stderr.strip() or plan.stdout.strip()}")
        if "version-iteration-advance: plan" not in plan.stdout:
            errors.append("advance plan must report plan status")
        if evidence_dir.exists() or history_dir.exists():
            errors.append("advance plan must not create evidence or history directories")

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
        if run.returncode != 0:
            errors.append(f"advance run failed: {run.stderr.strip() or run.stdout.strip()}")
            payload = {}
        else:
            payload = json.loads(run.stdout)
        if payload.get("schemaVersion") != "kube-actuary.version-iteration-advance.v1":
            errors.append("advance schemaVersion mismatch")
        if payload.get("status") != "passed" or payload.get("mode") != "run":
            errors.append("advance run must pass in run mode")
        if payload.get("runner", {}).get("status") != "passed":
            errors.append("advance must include a passing next-task runner result")
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
        if payload.get("history", {}).get("runs") != 2:
            errors.append("advance history status must include two runs")

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

        output = tmpdir / "advance.json"
        written = run_script(ADVANCE, str(evidence_dir), str(history_dir / "plan-only"), "--format", "json", "--output", str(output))
        if written.returncode != 0 or not output.is_file():
            errors.append("advance plan must write requested output file")

    for path in (README, README_KO, TASKBOARD, LIVE_VALIDATION):
        text = path.read_text()
        for snippet in ("advance_version_iteration.py", "kube-actuary.version-iteration-advance.v1"):
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
