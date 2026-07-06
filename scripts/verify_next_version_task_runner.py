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


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        evidence_dir = tmpdir / "evidence"
        recorded_dir = tmpdir / "recorded"
        prepared = run_script(PREPARE, str(evidence_dir))
        raw = evidence_dir / "raw" / "01-controller-resource-budget-kubectl-top.txt"
        supplemental = evidence_dir / "supplemental" / "01-controller-resource-budget-external-2.json"
        if prepared.returncode != 0:
            errors.append(f"prepare evidence dir failed: {prepared.stderr.strip() or prepared.stdout.strip()}")

        plan = run_script(RUNNER, str(evidence_dir))
        if plan.returncode != 0:
            errors.append(f"runner plan failed: {plan.stderr.strip() or plan.stdout.strip()}")
        if "next-version-task-run: plan" not in plan.stdout:
            errors.append("runner plan must report plan status")
        if raw.exists() or supplemental.exists():
            errors.append("runner plan must not write evidence files")

        run_env = fake_tool_env(tmpdir / "tools")
        run = run_script(RUNNER, str(evidence_dir), "--run", "--format", "json", env=run_env)
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
        else:
            recorded_payload = json.loads(recorded_json.read_text())
            if "# KubeActuary Next Version Task Run" not in recorded_md.read_text():
                errors.append("runner recorded Markdown must include the run report title")
        if recorded_payload.get("schemaVersion") != "kube-actuary.next-version-task-run.v1":
            errors.append("runner recorded JSON schemaVersion mismatch")
        if recorded_payload.get("status") != "passed" or recorded_payload.get("mode") != "run":
            errors.append("runner recorded JSON must preserve passed run status")
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
    print("record: metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
